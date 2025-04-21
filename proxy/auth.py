import hashlib

from fastapi import HTTPException

from .redeem import redeem
from .db import ApiKey, create_session, RECIEIVE_LN_ADDRESS, COST_PER_REQUEST


def _hash_api_key(api_key: str) -> str:
    """Hashes the API key using SHA256."""
    return hashlib.sha256(api_key.encode()).hexdigest()


async def validate_api_key(api_key: str) -> None:
    """
    Validates the provided API key using SQLModel.
    If it's a cashu key, it redeems it and stores its hash and balance.
    Otherwise checks if the hash of the key exists.
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="api-key or cashu-token required")

    hashed_key = _hash_api_key(api_key)

    async with create_session() as session:
        # check if key exists
        if await session.get(ApiKey, hashed_key):
            return

        # If hash not found, check if it's a potentially new cashu key
        if api_key.startswith("cashu"):
            try:
                print(
                    f"Attempting to redeem cashu key: {api_key[:15]}...{api_key[-15:]}"
                )
                # Redeem the original cashu key
                amount = await redeem(api_key, RECIEIVE_LN_ADDRESS)
                print(f"Redeemed successfully. Amount: {amount}")
                # Store the hash and the redeemed amount using SQLModel
                new_key = ApiKey(hashed_key=hashed_key, balance=amount)
                session.add(new_key)
                await session.commit()
                await session.refresh(new_key)
                return
            except Exception as e:
                print(f"Redemption failed: {e}")
                # Include the redemption error message for better debugging
                raise HTTPException(
                    status_code=401, detail=f"Invalid or expired cashu key: {e}"
                )

        # If it's not a known hash and not a valid new cashu key
        raise HTTPException(status_code=401, detail="Invalid API key")


async def pay_for_request(api_key: str) -> None:
    """Deducts the cost of a request from the balance associated with the API key hash using SQLModel."""
    hashed_key = _hash_api_key(api_key)

    # Get the key record using SQLModel
    async with create_session() as session:
        key_record = await session.get(ApiKey, hashed_key)

        if key_record is None:
            # This should theoretically not happen if validate_api_key was called first
            # Consider adding a check or relying on validate_api_key structure
            raise HTTPException(status_code=401, detail="API key not validated")

        if key_record.balance < COST_PER_REQUEST:
            raise HTTPException(
                status_code=402, detail="Insufficient balance"
            )  # 402 Payment Required

        # todo: COST_PER_INPUT_TOKENS + COST_PER_OUTPUT_TOKENS (like openai)
        key_record.balance -= COST_PER_REQUEST
        session.add(key_record)  # Mark the object as changed
        await session.commit()
        await session.refresh(key_record)

        print(
            f"Charged {COST_PER_REQUEST}. New balance for key hash {hashed_key[:10]}...: {key_record.balance}"
        )
