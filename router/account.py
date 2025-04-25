from typing import Annotated
from fastapi import APIRouter, Header, HTTPException

from .auth import validate_api_key

account_router = APIRouter(prefix="/account")


@account_router.get("/")
async def account_info(authorization: Annotated[str, Header(...)]) -> dict:
    if authorization.startswith("Bearer "):
        if key := await validate_api_key(authorization[7:]):
            return {
                "balance": key.balance,
                "api_key": "sk-" + key.hashed_key,
            }

    raise HTTPException(
        status_code=401,
        detail="Invalid authorization. Use 'Bearer <cashu-token>' or 'Bearer <api-key>'",
    )


@account_router.post("/topup")
async def topup_balance(cashu_token: str):
    return {"todo": "implement"}


@account_router.post("/refund")
async def refund_balance(lightning_address: str):
    return {"todo": "implement"}
