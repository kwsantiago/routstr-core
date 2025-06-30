from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from router.models import MODELS, Model

models_router = APIRouter(prefix="/proxy")


class ProxyModelFromApi(BaseModel):
    name: str
    input_cost: Optional[float] = None
    output_cost: Optional[float] = None
    min_cash_per_request: Optional[float] = None
    min_cost_per_request: Optional[float] = None
    provider: Optional[str] = None
    soft_deleted: Optional[bool] = None
    model_type: Optional[str] = None
    description: Optional[str] = None
    context_length: Optional[int] = None
    is_free: Optional[bool] = None


def convert_model_to_proxy_format(model: Model) -> ProxyModelFromApi:
    input_cost = None
    output_cost = None
    min_cash_per_request = None
    min_cost_per_request = None
    is_free = None

    if model.sats_pricing:
        input_cost = model.sats_pricing.prompt * 1000 * 1_000_000
        output_cost = model.sats_pricing.completion * 1000 * 1_000_000
        min_cash_per_request = (
            model.sats_pricing.request * 1000 if model.sats_pricing.request else 0
        )
        min_cost_per_request = model.sats_pricing.max_cost * 1000

        is_free = (
            model.sats_pricing.prompt == 0
            and model.sats_pricing.completion == 0
            and model.sats_pricing.request == 0
        )

    return ProxyModelFromApi(
        name=model.id,
        input_cost=input_cost,
        output_cost=output_cost,
        min_cash_per_request=min_cash_per_request,
        min_cost_per_request=min_cost_per_request,
        provider=None,
        model_type=model.architecture.modality,
        description=model.description,
        context_length=model.context_length,
        is_free=is_free,
    )


@models_router.get("/models")
async def get_models() -> List[ProxyModelFromApi]:
    return [convert_model_to_proxy_format(model) for model in MODELS]
