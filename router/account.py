from typing import Annotated
from fastapi import APIRouter, Header, HTTPException, Depends
from sixty_nuts import Wallet

from .auth import validate_bearer_key
from .cashu import refund_balance, credit_balance, NSEC, MINT
from .db import ApiKey, AsyncSession, get_session

account_router = APIRouter(prefix="/v1/wallet")


async def get_key_from_header(
    authorization: Annotated[str, Header(...)],
    session: AsyncSession = Depends(get_session),
) -> ApiKey:
    if authorization.startswith("Bearer "):
        return await validate_bearer_key(authorization[7:], session)

    raise HTTPException(
        status_code=401,
        detail="Invalid authorization. Use 'Bearer <cashu-token>' or 'Bearer <api-key>'",
    )


@account_router.get("/")
async def account_info(key: ApiKey = Depends(get_key_from_header)) -> dict:
    return {
        "api_key": "sk-" + key.hashed_key,
        "balance": key.balance,
    }


@account_router.post("/topup")
async def topup_balance_endpoint(
    cashu_token: str,
    key: ApiKey = Depends(get_key_from_header),
    session: AsyncSession = Depends(get_session),
):
    return await credit_balance(cashu_token, key, session)


@account_router.post("/refund")
async def refund_balance_endpoint(
    key: ApiKey = Depends(get_key_from_header),
    session: AsyncSession = Depends(get_session),
) -> dict:
    remaining_balance = key.balance
    key.balance = 0
    session.add(key)
    await session.commit()
    if key.refund_address:
        await refund_balance(remaining_balance, key, session)
        return {"recipient": key.refund_address, "msats": remaining_balance}
    else:
        async with Wallet(nsec=NSEC, mint_urls=[MINT]) as wallet:
            token = await wallet.send(remaining_balance)
            return {"msats": remaining_balance, "recipient": None, "token": token}
