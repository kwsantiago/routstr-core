import asyncio
import os
import json
from fastapi import APIRouter, Request, BackgroundTasks, Depends
from fastapi.responses import Response, StreamingResponse
import httpx
import re

from router.cashu import pay_out_with_new_session

from .auth import validate_bearer_key, pay_for_request, adjust_payment_for_tokens
from .db import AsyncSession, get_session

UPSTREAM_BASE_URL = os.environ["UPSTREAM_BASE_URL"]
UPSTREAM_API_KEY = os.environ.get("UPSTREAM_API_KEY", "")

proxy_router = APIRouter()


@proxy_router.api_route(
    "/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"]
)
async def proxy(
    request: Request, path: str, session: AsyncSession = Depends(get_session)
):
    auth = request.headers.get("Authorization", "")
    bearer_key = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""

    key = await validate_bearer_key(bearer_key, session)
    await pay_for_request(key, session, request)

    # Prepare headers, removing sensitive/problematic ones
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)

    if UPSTREAM_API_KEY:
        headers["Authorization"] = f"Bearer {UPSTREAM_API_KEY}"
        headers.pop("authorization", None)
    else:
        headers.pop("Authorization", None)
        headers.pop("authorization", None)

    if path.startswith("v1/"):
        path = path.replace("v1/", "")

    url = f"{UPSTREAM_BASE_URL}/{path}"
    client = httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(retries=1))

    try:
        response = await client.send(
            client.build_request(
                request.method,
                url,
                headers=headers,
                content=request.stream(),
                params=request.query_params,
            ),
            stream=True,
        )

        # For chat completions, we need to handle token-based pricing
        if path.endswith("chat/completions"):
            # Handle both streaming and non-streaming responses
            content_type = response.headers.get("content-type", "")
            is_streaming = "text/event-stream" in content_type

            if is_streaming and response.status_code == 200:
                # Process streaming response and extract cost from the last chunk
                async def stream_with_cost():
                    # Store all chunks to analyze
                    stored_chunks = []
                    usage_data_found = False

                    async for chunk in response.aiter_bytes():
                        # Store chunk for later analysis
                        stored_chunks.append(chunk)

                        # Pass through each chunk to client
                        yield chunk

                    # Process stored chunks to find usage data
                    # Start from the end and work backwards
                    for i in range(len(stored_chunks) - 1, -1, -1):
                        chunk = stored_chunks[i]
                        if not chunk or chunk == b"":
                            continue

                        try:
                            # Split by "data: " to get individual SSE events
                            events = re.split(b"data: ", chunk)
                            for event_data in events:
                                if (
                                    not event_data
                                    or event_data.strip() == b"[DONE]"
                                    or event_data.strip() == b""
                                ):
                                    continue

                                try:
                                    data = json.loads(event_data)
                                    if (
                                        "usage" in data
                                        and data["usage"] is not None
                                        and isinstance(data["usage"], dict)
                                    ):
                                        # Found usage data, calculate cost
                                        cost_data = await adjust_payment_for_tokens(
                                            key, data, session
                                        )
                                        # Format as SSE and yield
                                        cost_json = json.dumps({"cost": cost_data})
                                        yield f"data: {cost_json}\n\n".encode()
                                        usage_data_found = True
                                        break
                                except json.JSONDecodeError:
                                    continue
                            
                        except Exception as e:
                            print(f"Error processing streaming response for cost: {e}")

                background_tasks = BackgroundTasks()
                background_tasks.add_task(response.aclose)
                background_tasks.add_task(client.aclose)

                return StreamingResponse(
                    stream_with_cost(),
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    background=background_tasks,
                )

            elif response.status_code == 200 and "application/json" in content_type:
                # Handle non-streaming response
                try:
                    content = await response.aread()
                    response_json = json.loads(content)
                    cost_data = await adjust_payment_for_tokens(
                        key, response_json, session
                    )
                    response_json["cost"] = cost_data
                    return Response(
                        content=json.dumps(response_json).encode(),
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type="application/json",
                    )
                except json.JSONDecodeError as e:
                    print(f"Failed to parse JSON from upstream response: {e}")
                except Exception as e:
                    print(f"Error adjusting payment for tokens: {e}")
                finally:
                    await response.aclose()
                    await client.aclose()

        # For all other responses, stream the response
        background_tasks = BackgroundTasks()
        background_tasks.add_task(response.aclose)
        background_tasks.add_task(client.aclose)
        background_tasks.add_task(pay_out_with_new_session)

        return StreamingResponse(
            response.aiter_bytes(),
            status_code=response.status_code,
            headers=dict(response.headers),
            background=background_tasks,
        )

    except httpx.RequestError as exc:
        await client.aclose()
        print(
            f"Error forwarding request to upstream: {exc}\n"
            f"Request details: method={request.method}, url={url}, headers={headers}, "
            f"path={path}, query_params={dict(request.query_params)}"
        )
        return Response(
            content=f"Error connecting to upstream service: {exc}",
            status_code=502,
        )
    except Exception as exc:
        await client.aclose()
        import traceback
        tb = traceback.format_exc()
        print(
            f"Unexpected error: {exc}\n"
            f"Request details: method={request.method}, url={url}, headers={headers}, "
            f"path={path}, query_params={dict(request.query_params)}\n"
            f"Traceback:\n{tb}"
        )
        return Response(
            content=f"Unexpected server error: {exc}",
            status_code=500,
        )
