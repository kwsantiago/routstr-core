import hashlib
import json
import os
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

from .cashu import credit_balance, pay_out
from .db import ApiKey, AsyncSession
from .price import btc_usd_ask_price

COST_PER_REQUEST = (
    int(os.environ.get("COST_PER_REQUEST", "1")) * 1000
)  # Convert to msats
COST_PER_1K_INPUT_TOKENS = (
    int(os.environ.get("COST_PER_1K_INPUT_TOKENS", "0")) * 1000
)  # Convert to msats
COST_PER_1K_OUTPUT_TOKENS = (
    int(os.environ.get("COST_PER_1K_OUTPUT_TOKENS", "0")) * 1000
)  # Convert to msats
MODEL_BASED_PRICING = os.environ.get("MODEL_BASED_PRICING", "false").lower() == "true"


async def validate_bearer_key(bearer_key: str, session: AsyncSession) -> ApiKey:
    """
    Validates the provided API key using SQLModel.
    If it's a cashu key, it redeems it and stores its hash and balance.
    Otherwise checks if the hash of the key exists.
    """
    if not bearer_key:
        raise HTTPException(status_code=401, detail="api-key or cashu-token required")

    if bearer_key.startswith("sk-"):
        if exsisting_key := await session.get(ApiKey, bearer_key[3:]):
            return exsisting_key

    if bearer_key.startswith("cashu"):
        try:
            hashed_key = hashlib.sha256(bearer_key.encode()).hexdigest()
            if exsisting_key := await session.get(ApiKey, hashed_key):
                return exsisting_key
            new_key = ApiKey(hashed_key=hashed_key, balance=0)
            await credit_balance(bearer_key, new_key, session)
            await session.refresh(new_key)
            return new_key
        except Exception as e:
            print(f"Redemption failed: {e}")
            raise HTTPException(
                status_code=401, detail=f"Invalid or expired cashu key: {e}"
            )
    raise HTTPException(status_code=401, detail="Invalid API key")


async def pay_for_request(key: ApiKey, session: AsyncSession) -> None:
    if key.balance < COST_PER_REQUEST:
        raise HTTPException(status_code=402, detail="Insufficient balance")

    # Charge the base cost for the request
    key.balance -= COST_PER_REQUEST
    key.total_spent += COST_PER_REQUEST
    key.total_requests += 1
    session.add(key)
    await session.commit()
    await session.refresh(key)


async def adjust_payment_for_tokens(
    key: ApiKey, response_data: dict, session: AsyncSession
) -> dict:
    """
    Adjusts the payment based on token usage in the response.
    This is called after the initial payment and the upstream request is complete.
    Returns cost data to be included in the response.
    """
    cost_data = {
        "base_msats": COST_PER_REQUEST,
        "input_msats": 0,
        "output_msats": 0,
        "total_msats": COST_PER_REQUEST,
    }
    if MODEL_BASED_PRICING and os.path.exists("models.json"):
        models = read_models()
        response_model = response_data.get("model", "")
        if response_model not in [model.name for model in models]:
            raise HTTPException(status_code=400, detail="Invalid model")
        model = next(model for model in models if model.name == response_model)
        MSATS_PER_1K_INPUT_TOKENS = await model.msats_per_1k_input_tokens()
        MSATS_PER_1K_OUTPUT_TOKENS = await model.msats_per_1k_output_tokens()

    if not (MSATS_PER_1K_OUTPUT_TOKENS and MSATS_PER_1K_INPUT_TOKENS):
        raise HTTPException(status_code=400, detail="Model pricing not defined")

    input_tokens = response_data.get("usage", {}).get("prompt_tokens", 0)
    output_tokens = response_data.get("usage", {}).get("completion_tokens", 0)

    input_msats = int(round(input_tokens / 1000 * MSATS_PER_1K_INPUT_TOKENS, 0))
    output_msats = int(round(output_tokens / 1000 * MSATS_PER_1K_OUTPUT_TOKENS, 0))
    token_based_cost = int(round(input_msats + output_msats, 0))

    cost_data["base_msats"] = 0
    cost_data["input_msats"] = input_msats
    cost_data["output_msats"] = output_msats
    cost_data["total_msats"] = token_based_cost

    # If token-based pricing is enabled and base cost is 0, use token-based cost
    # Otherwise, token cost is additional to the base cost
    cost_difference = token_based_cost - COST_PER_REQUEST

    if cost_difference == 0:
        return cost_data  # No adjustment needed

    if cost_difference > 0:
        # Need to charge more
        if key.balance < cost_difference:
            print(
                f"Warning: Insufficient balance for token-based pricing adjustment: {key.hashed_key[:10]}..."
            )
            # Still proceed but log the issue - we already provided the service
        else:
            key.balance -= cost_difference
            key.total_spent += cost_difference
            cost_data["total_msats"] = COST_PER_REQUEST + cost_difference
    else:
        # Refund some of the base cost
        refund = abs(cost_difference)
        key.balance += refund
        key.total_spent -= refund
        cost_data["total_msats"] = COST_PER_REQUEST - refund

    session.add(key)
    await session.commit()

    await pay_out(session)

    return cost_data


class LLModel(BaseModel):
    name: str
    cost_per_1m_input_tokens: float = Field(alias="cost_per_1m_prompt_tokens")
    cost_per_1m_output_tokens: float = Field(alias="cost_per_1m_completion_tokens")
    currency: Literal["btc", "usd"]

    async def msats_per_1k_input_tokens(self) -> float:
        if self.currency == "btc":
            return self.cost_per_1m_input_tokens * 100_000
        btc_price = await btc_usd_ask_price()
        return (self.cost_per_1m_input_tokens / 1000) * (100_000_000_000 / btc_price)

    async def msats_per_1k_output_tokens(self) -> float:
        if self.currency == "btc":
            return self.cost_per_1m_output_tokens * 100_000
        btc_price = await btc_usd_ask_price()
        return (self.cost_per_1m_output_tokens / 1000) * (100_000_000_000 / btc_price)


def read_models() -> list[LLModel]:
    if not os.path.exists("models.json"):
        raise HTTPException(status_code=400, detail="Models not defined")
    with open("models.json", "r") as f:
        models = json.load(f)["models"]
    return [LLModel(**model) for model in models]
