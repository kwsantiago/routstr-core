from typing import List

from fastapi import APIRouter

from router.models import MODELS, Model

models_router = APIRouter(prefix="/api/proxy")


@models_router.get("/models")
async def get_models() -> List[Model]:
    return MODELS
