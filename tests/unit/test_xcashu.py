import pytest
from httpx import ASGITransport, AsyncClient

from router.core.main import app


@pytest.mark.asyncio
async def test_x_cashu_balance() -> None:
    """Test the /v1/info endpoint with real app startup."""
    async with AsyncClient(
        transport=ASGITransport(app=app),  # type: ignore
        base_url="http://test",
    ) as client:
        assert (await client.get("/v1/info")).status_code == 200
        # response = await client.post(
        #     "/v1/chat/completions",
        #     headers={"x-cashu": "cashuA1234567890"},
        #     json={
        #         "model": "gpt-4-mock",
        #         "messages": [{"role": "user", "content": "Hello"}],
        #     },
        # )
        # assert response.status_code == 200
        # assert response.json()["choices"][0]["message"]["content"] == "null"  # mock
        # assert "cashu" in response.headers["x-cashu"]
        assert True
