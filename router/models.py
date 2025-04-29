import asyncio
import json
from pydantic.v1 import BaseModel

from .price import sats_usd_ask_price


class Architecture(BaseModel):
    modality: str
    input_modalities: list[str]
    output_modalities: list[str]
    tokenizer: str
    instruct_type: str | None


class Pricing(BaseModel):
    prompt: float
    completion: float
    request: float
    image: float
    web_search: float
    internal_reasoning: float


class Model(BaseModel):
    id: str
    name: str
    created: int
    description: str
    context_length: int
    architecture: Architecture
    pricing: Pricing
    sats_pricing: Pricing | None
    per_request_limits: dict | None


MODELS: list[Model] = []

with open("models.json", "r") as f:
    MODELS = [Model(**model) for model in json.load(f)["models"]]


async def update_sats_pricing() -> None:
    while True:
        sats_to_usd = await sats_usd_ask_price()
        for model in MODELS:
            model.sats_pricing = Pricing(
                **{k: v / sats_to_usd for k, v in model.pricing.dict().items()}
            )
        await asyncio.sleep(10)
