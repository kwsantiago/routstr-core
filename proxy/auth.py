import hashlib
import json
import os
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel

from .redeem import redeem
from .db import (
    ApiKey,
    create_session,
    RECIEIVE_LN_ADDRESS,
    COST_PER_REQUEST,
    COST_PER_1K_PROMPT_TOKENS,
    COST_PER_1K_COMPLETION_TOKENS,
    MODEL_BASED_PRICING,
)


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
                amount_msats = amount * 1000  # Convert sats to msats
                print(
                    f"Redeemed successfully. Amount: {amount} sats ({amount_msats} msats)"
                )
                # Store the hash and the redeemed amount using SQLModel
                new_key = ApiKey(hashed_key=hashed_key, balance=amount_msats)
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

        # Charge the base cost for the request
        key_record.balance -= COST_PER_REQUEST
        key_record.total_spent += COST_PER_REQUEST
        key_record.total_requests += 1
        session.add(key_record)  # Mark the object as changed
        await session.commit()
        await session.refresh(key_record)

        print(
            f"Charged {COST_PER_REQUEST} msats. New balance for key hash {hashed_key[:10]}...: {key_record.balance} msats"
        )


async def adjust_payment_for_tokens(api_key: str, response_data: dict) -> dict:
    """
    Adjusts the payment based on token usage in the response.
    This is called after the initial payment and the upstream request is complete.
    Returns cost data to be included in the response.
    """
    cost_data = {
        "base_cost_msats": COST_PER_REQUEST,
        "prompt_cost_msats": 0,
        "completion_cost_msats": 0,
        "total_cost_msats": COST_PER_REQUEST,
    }
    if MODEL_BASED_PRICING and os.path.exists("models.json"):
        offering = Offering.validate(json.load(open("models.json")))
        models = offering.models
        response_model = response_data.get("model", "")
        if response_model not in [model.name for model in models]:
            raise HTTPException(status_code=400, detail="Invalid model")
        model = next(model for model in models if model.name == response_model)
        prompt_tokens = response_data.get("usage", {}).get("prompt_tokens", 0)
        completion_tokens = response_data.get("usage", {}).get("completion_tokens", 0)
        cost_data["base_cost_msats"] = 0
        cost_data["prompt_cost_msats"] = int(
            prompt_tokens / 1000 * model.msats_per_1k_prompt_tokens + 0.999
        )
        cost_data["completion_cost_msats"] = int(
            completion_tokens / 1000 * model.msats_per_1k_completion_tokens + 0.999
        )
        cost_data["total_cost_msats"] = int(
            cost_data["prompt_cost_msats"] + cost_data["completion_cost_msats"]
        )
        print(cost_data)
    if not (COST_PER_1K_PROMPT_TOKENS or COST_PER_1K_COMPLETION_TOKENS):
        return cost_data  # Skip if token-based pricing is not enabled

    # Extract token usage from response
    usage = response_data.get("usage", {})
    if not usage:
        return cost_data  # No token usage information available

    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)

    # Calculate token-based cost
    prompt_cost = (prompt_tokens / 1000) * COST_PER_1K_PROMPT_TOKENS
    completion_cost = (completion_tokens / 1000) * COST_PER_1K_COMPLETION_TOKENS
    token_based_cost = int(prompt_cost + completion_cost)

    cost_data["base_cost_msats"] = 0
    cost_data["prompt_cost_msats"] = int(prompt_cost)
    cost_data["completion_cost_msats"] = int(completion_cost)
    cost_data["total_cost_msats"] = token_based_cost

    # If token-based pricing is enabled and base cost is 0, use token-based cost
    # Otherwise, token cost is additional to the base cost
    cost_difference = token_based_cost - COST_PER_REQUEST

    if cost_difference == 0:
        return cost_data  # No adjustment needed

    hashed_key = _hash_api_key(api_key)

    async with create_session() as session:
        key_record = await session.get(ApiKey, hashed_key)

        if key_record is None:
            print(
                f"Warning: API key not found when adjusting payment: {hashed_key[:10]}..."
            )
            return cost_data

        if cost_difference > 0:
            # Need to charge more
            if key_record.balance < cost_difference:
                print(
                    f"Warning: Insufficient balance for token-based pricing adjustment: {hashed_key[:10]}..."
                )
                # Still proceed but log the issue - we already provided the service
            else:
                key_record.balance -= cost_difference
                key_record.total_spent += cost_difference
                print(
                    f"Additional charge for tokens: {cost_difference} msats. New balance: {key_record.balance} msats"
                )
                cost_data["total_cost_msats"] = COST_PER_REQUEST + cost_difference
        else:
            # Refund some of the base cost
            refund = abs(cost_difference)
            key_record.balance += refund
            key_record.total_spent -= refund
            print(
                f"Refund for tokens: {refund} msats. New balance: {key_record.balance} msats"
            )
            cost_data["total_cost_msats"] = COST_PER_REQUEST - refund

        session.add(key_record)
        await session.commit()

    return cost_data


def convert_usd_to_btc(usd: float) -> float:
    EXCHANGE_FEE = 0.005
    BTC_PRICE = 93000
    return usd / BTC_PRICE * (1 - EXCHANGE_FEE)


class LLModel(BaseModel):
    name: str
    cost_per_1m_prompt_tokens: float
    cost_per_1m_completion_tokens: float
    currency: Literal["btc", "usd"]

    @property
    def msats_per_1k_prompt_tokens(self) -> float:
        if self.currency == "btc":
            return self.cost_per_1m_prompt_tokens * 100_000_000
        return convert_usd_to_btc(self.cost_per_1m_prompt_tokens) * 100_000_000

    @property
    def msats_per_1k_completion_tokens(self) -> float:
        if self.currency == "btc":
            return self.cost_per_1m_completion_tokens * 100_000_000
        return convert_usd_to_btc(self.cost_per_1m_completion_tokens) * 100_000_000


class Offering(BaseModel):
    # npub: str
    models: list[LLModel]
