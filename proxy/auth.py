import json
import os
import hashlib
from fastapi import HTTPException
from .redeem import redeem

ACTIVE_KEYS_FILE = "active_keys.json"
# These are needed here because validate_api_key and pay_for_request use them
RECIEIVE_LN_ADDRESS = os.environ["RECIEIVE_LN_ADDRESS"]
COST_PER_REQUEST = int(os.environ["COST_PER_REQUEST"])


def _hash_api_key(api_key: str) -> str:
    """Hashes the API key using SHA256."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def _load_active_keys() -> dict[str, int]:
    """Loads the active keys (hashed) and their balances from the JSON file."""
    try:
        with open(ACTIVE_KEYS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Return empty dict if file not found or empty/invalid JSON
        return {}


def _save_active_keys(active_keys: dict[str, int]) -> None:
    """Saves the active keys (hashed) and their balances to the JSON file."""
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(ACTIVE_KEYS_FILE) or ".", exist_ok=True)
    with open(ACTIVE_KEYS_FILE, "w") as f:
        json.dump(active_keys, f, indent=2)  # Add indent for readability


async def validate_api_key(api_key: str) -> None:
    """
    Validates the provided API key.
    If it's a cashu key, it redeems it and stores its hash and balance.
    Otherwise checks if the hash of the key exists.
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    hashed_key = _hash_api_key(api_key)
    active_keys = _load_active_keys()

    if hashed_key in active_keys:
        # Key hash already exists, it's valid (might be cashu or other type)
        return

    # If hash not found, check if it's a potentially new cashu key
    if api_key.startswith("cashu"):
        try:
            print(f"Attempting to redeem cashu key: {api_key[:15]}...{api_key[-15:]}")
            # Redeem the original cashu key
            amount = await redeem(api_key, RECIEIVE_LN_ADDRESS)
            print(f"Redeemed successfully. Amount: {amount}")
            # Store the hash and the redeemed amount
            active_keys[hashed_key] = amount
            _save_active_keys(active_keys)
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
    """Deducts the cost of a request from the balance associated with the API key hash."""
    hashed_key = _hash_api_key(api_key)
    active_keys = _load_active_keys()

    if hashed_key not in active_keys:
        # This should theoretically not happen if validate_api_key was called first
        raise HTTPException(status_code=401, detail="API key not validated")

    if active_keys[hashed_key] < COST_PER_REQUEST:
        raise HTTPException(
            status_code=402, detail="Insufficient balance"
        )  # 402 Payment Required

    # todo: COST_PER_INPUT_TOKENS + COST_PER_OUTPUT_TOKENS (like openai)
    active_keys[hashed_key] -= COST_PER_REQUEST
    _save_active_keys(active_keys)
    print(
        f"Charged {COST_PER_REQUEST}. New balance for key hash {hashed_key[:10]}...: {active_keys[hashed_key]}"
    )
