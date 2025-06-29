import json
import traceback
from typing import Literal, cast

import httpx
from fastapi import BackgroundTasks, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from router.cashu import wallet
from router.payment.cost_caculation import (CostData, CostDataError,
                                            MaxCostData, calculate_cost)
from router.payment.helpers import (UPSTREAM_BASE_URL, check_token_balance,
                                    create_error_response,
                                    get_max_cost_for_model,
                                    prepare_upstream_headers)

type Currency = Literal["sat", "msat"]

async def x_cashu_handler(
    request: Request, x_cashu_token: str, path: str
) -> Response | StreamingResponse:
    print(x_cashu_token)
    headers = dict(request.headers)

    # amount, _ = await redeem_token(x_cashu_token)
    # print(amount)

    headers = prepare_upstream_headers(dict(request.headers))
    return await forward_to_upstream(request, path, headers, 1000)


async def forward_to_upstream(
    request: Request, path: str, headers: dict, amount: int
) -> Response | StreamingResponse:
    print(path, amount)
    """Forward request to upstream and handle the response."""
    if path.startswith("v1/"):
        path = path.replace("v1/", "")

    url = f"{UPSTREAM_BASE_URL}/{path}"
    async with httpx.AsyncClient(
        transport=httpx.AsyncHTTPTransport(retries=1),
        timeout=None,
    ) as client:
        print(url)
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

            if path.endswith("chat/completions"):
                result = await handle_x_cashu_chat_completion(response, amount)
                background_tasks = BackgroundTasks()
                background_tasks.add_task(response.aclose)
                result.background = background_tasks
                return result

            background_tasks = BackgroundTasks()
            background_tasks.add_task(response.aclose)
            background_tasks.add_task(client.aclose)

            return StreamingResponse(
                response.aiter_bytes(),
                status_code=response.status_code,
                headers=dict(response.headers),
                background=background_tasks,
            )
        except Exception as exc:
            tb = traceback.format_exc()
            print(
                f"Unexpected error: {exc}\n"
                f"Request details: method={request.method}, url={url}, headers={headers}, "
                f"path={path}, query_params={dict(request.query_params)}\n"
                f"Traceback:\n{tb}"
            )
            return create_error_response(
                "internal_error", "An unexpected server error occurred", 500
            )


async def handle_x_cashu_chat_completion(
    response: httpx.Response, amount: int
) -> StreamingResponse | Response:
    """Handle non-streaming chat completion responses with token-based pricing."""
    try:
        content = await response.aread()
        print(response)
        response_json = json.loads(content)
        print(response_json, amount)
        cost_data = await get_cost(response_json)

        if not cost_data:
            # response.headers["X-Cashu"] = await send_refund(amount)
            return Response(
                content=json.dumps(
                    {
                        "error": {
                            "message": "Error forwarding request to upstream",
                            "type": "upstream_error",
                            "code": response.status_code,
                        }
                    }
                ),
                status_code=response.status_code,
                media_type="application/json",
            )

        response_headers = dict(response.headers)

        if "transfer-encoding" in response_headers:
            del response_headers["transfer-encoding"]

        if "content-encoding" in response_headers:
            del response_headers["content-encoding"]

        refund_token = await send_refund(amount - cost_data.total_msats)
        # response.headers["X-Cashu"] = refund_token

        return StreamingResponse(
            content=response.aiter_bytes(),
            status_code=response.status_code,
            headers=response_headers,
            media_type="application/json",
        )
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON from upstream response: {e}")
        raise
    except Exception as e:
        print(f"Error adjusting payment for tokens: {e}")
        raise


async def get_cost(response_data: dict) -> MaxCostData | CostData | None:
    """
    Adjusts the payment based on token usage in the response.
    This is called after the initial payment and the upstream request is complete.
    Returns cost data to be included in the response.
    """
    max_cost = get_max_cost_for_model(model=response_data["model"])

    match calculate_cost(response_data, max_cost):
        case MaxCostData() as cost:
            return cost
        case CostData() as cost:
            return cost
        case CostDataError() as error:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "message": error.message,
                        "type": "invalid_request_error",
                        "code": error.code,
                    }
                },
            )


async def redeem_token(x_cashu_token) -> tuple[int, Currency]:
    try:
        result = await wallet().redeem(x_cashu_token)
        return cast(tuple[int, Currency], result)
    except Exception as e:
        print(f"Redemption failed: {e}")
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": f"Invalid or expired Cashu key: {str(e)}",
                    "type": "invalid_request_error",
                    "code": "invalid_api_key",
                }
            },
        )


async def send_refund(amount) -> str:
    try:
        return await wallet().send(amount)
    except Exception as e:
        print(f"send failed: {e}")
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": f"failed to create refund: {str(e)}",
                    "type": "invalid_request_error",
                    "code": "send_token_failed",
                }
            },
        )

