import os
from fastapi import FastAPI, Request, HTTPException
import httpx
from .auth import validate_api_key, pay_for_request
from fastapi.responses import Response

UPSTREAM_BASE_URL = os.environ["UPSTREAM_BASE_URL"]
UPSTREAM_API_KEY = os.environ.get("UPSTREAM_API_KEY", "")

app = FastAPI()


@app.api_route(
    "/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"]
)
async def proxy(request: Request, path: str):
    auth = request.headers.get("Authorization", "")
    api_key = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""

    print(f"Validating API key: {api_key[:10]}...{api_key[-10:]}")
    await validate_api_key(api_key)

    await pay_for_request(api_key)

    # Prepare request data
    body: bytes | None = await request.body()
    if not body:
        body = None

    # Prepare headers, removing sensitive/problematic ones
    forward_headers = dict(request.headers)
    if UPSTREAM_API_KEY:
        forward_headers["Authorization"] = f"Bearer {UPSTREAM_API_KEY}"
        forward_headers.pop("authorization", None)
    else:
        forward_headers.pop("Authorization", None)
        forward_headers.pop("authorization", None)
    forward_headers.pop("host", None)
    forward_headers.pop("content-length", None)

    if path.startswith("v1/"):
        path = path.replace("v1/", "")

    async with httpx.AsyncClient(base_url=UPSTREAM_BASE_URL) as client:
        try:
            rp = await client.request(
                method=request.method,
                url=f"/{path}",
                headers=forward_headers,
                params=request.query_params,
                content=body,
                timeout=30.0,
            )

            print(f"Upstream response status: {rp.status_code}")

            # Filter response headers
            response_headers = dict(rp.headers)
            response_headers.pop("content-encoding", None)
            response_headers.pop("transfer-encoding", None)
            response_headers.pop("connection", None)

            # Return a streaming response or regular response based on upstream
            return Response(
                content=rp.content,
                status_code=rp.status_code,
                headers=response_headers,
            )

        except httpx.RequestError as exc:
            print(f"Error forwarding request to upstream: {exc}")
            raise HTTPException(
                status_code=502, detail=f"Error connecting to upstream service: {exc}"
            )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    print(f"Starting server on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
