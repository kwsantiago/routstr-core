import base64
import json
import os

import cbor2
from fastapi import HTTPException, Response
from sixty_nuts.types import CurrencyUnit

from router.models import MODELS
from router.payment.cost_caculation import COST_PER_REQUEST, MODEL_BASED_PRICING

UPSTREAM_BASE_URL = os.environ["UPSTREAM_BASE_URL"]
UPSTREAM_API_KEY = os.environ.get("UPSTREAM_API_KEY", "")


def get_cost_per_request(model: str | None = None) -> int:
    if MODEL_BASED_PRICING and MODELS and model:
        return get_max_cost_for_model(model=model)
    return COST_PER_REQUEST


def check_token_balance(headers: dict, body: dict) -> CurrencyUnit:
    if x_cashu := headers.get("x-cashu", None):
        cashu_token = x_cashu
    elif auth := headers.get("authorization", None):
        cashu_token = auth.split(" ")[1]
    else:
        raise HTTPException(status_code=401, detail="Unauthorized")
    cost = get_cost_per_request(model=body.get("model", None))
    if cashu_token.startswith("cashuA"):
        _token = base64_token_json(cashu_token)
        amount = sum(p["amount"] for t in _token["token"] for p in t["proofs"])
        unit: CurrencyUnit = _token["unit"]
        if unit == "sat":
            amount *= 1000
        if amount < cost:
            raise HTTPException(status_code=413, detail="Insufficient balance")
    elif cashu_token.startswith("cashuB"):
        _token = base64_token_cbor(cashu_token)
        amount = sum(p["a"] for t in _token["t"] for p in t["p"])
        unit = _token["u"]
        if unit == "sat":
            amount *= 1000
        if amount < cost:
            raise HTTPException(status_code=413, detail="Insufficient balance")
    else:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return unit


def base64_token_json(cashu_token: str) -> dict:
    # Version 3 - JSON format
    encoded = cashu_token[6:]  # Remove "cashuA"
    # Add correct padding – (-len) % 4 equals 0,1,2,3
    encoded += "=" * ((-len(encoded)) % 4)

    decoded = base64.urlsafe_b64decode(encoded).decode()
    token_data = json.loads(decoded)

    return token_data


def base64_token_cbor(cashu_token: str) -> dict:
    encoded = cashu_token[6:]  # Remove "cashuB"
    encoded += "=" * ((-len(encoded)) % 4)
    decoded_bytes = base64.urlsafe_b64decode(encoded)
    token_data = cbor2.loads(decoded_bytes)
    return token_data


def get_max_cost_for_model(model: str) -> int:
    if not MODEL_BASED_PRICING or not MODELS:
        return COST_PER_REQUEST
    if model not in [model.id for model in MODELS]:
        return COST_PER_REQUEST
    for m in MODELS:
        if m.id == model:
            return m.sats_pricing.max_cost * 1000  # type: ignore
    return COST_PER_REQUEST


def create_error_response(error_type: str, message: str, status_code: int) -> Response:
    """Create a standardized error response."""
    return Response(
        content=json.dumps(
            {
                "error": {
                    "message": message,
                    "type": error_type,
                    "code": status_code,
                }
            }
        ),
        status_code=status_code,
        media_type="application/json",
    )


def prepare_upstream_headers(request_headers: dict) -> dict:
    """Prepare headers for upstream request, removing sensitive/problematic ones."""
    headers = dict(request_headers)
    # Remove headers that shouldn't be forwarded
    headers.pop("host", None)
    headers.pop("content-length", None)
    headers.pop("refund-lnurl", None)
    headers.pop("key-expiry-time", None)
    headers.pop("x-cashu", None)

    # Handle authorization
    if UPSTREAM_API_KEY:
        headers["Authorization"] = f"Bearer {UPSTREAM_API_KEY}"
        headers.pop("authorization", None)
    else:
        headers.pop("Authorization", None)
        headers.pop("authorization", None)

    return headers
