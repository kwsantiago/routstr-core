import os
from typing import Literal

from cashu.core.base import Token
from cashu.wallet.helpers import deserialize_token_from_string, redeem_universal
from cashu.wallet.wallet import Wallet

from .db import DATABASE_URL, ApiKey, AsyncSession
from .logging import get_logger

# from .cashu import (
#     credit_balance,
#     delete_key_if_zero_balance,
#     refund_balance,
#     wallet,
# )
# from .cashu import (
#     check_for_refunds,
#     init_wallet,
#     periodic_payout,
# )

logger = get_logger(__name__)

RECEIVE_LN_ADDRESS = os.environ["RECEIVE_LN_ADDRESS"]
MINT = os.environ.get("MINT", "https://mint.minibits.cash/Bitcoin")
MINIMUM_PAYOUT = int(os.environ.get("MINIMUM_PAYOUT", 100))
REFUND_PROCESSING_INTERVAL = int(os.environ.get("REFUND_PROCESSING_INTERVAL", 3600))
PAYOUT_INTERVAL = int(os.environ.get("PAYOUT_INTERVAL", 300))  # Default 5 minutes
DEV_LN_ADDRESS = "routstr@minibits.cash"
DEVS_DONATION_RATE = float(os.environ.get("DEVS_DONATION_RATE", 0.021))  # 2.1%
NSEC = os.environ["NSEC"]  # Nostr private key for the wallet

logger.info(
    "Cashu module initialized",
    extra={
        "mint": MINT,
        "minimum_payout": MINIMUM_PAYOUT,
        "refund_processing_interval": REFUND_PROCESSING_INTERVAL,
        "payout_interval": PAYOUT_INTERVAL,
        "devs_donation_rate": DEVS_DONATION_RATE,
    },
)

CurrencyUnit = Literal["sat", "msat"]


async def get_balance(unit: CurrencyUnit) -> int:
    raise NotImplementedError


async def recieve_token(
    token: str,
) -> tuple[int, CurrencyUnit, str]:  # amount, unit, mint_url
    raise NotImplementedError


async def send_token(
    amount: int, unit: CurrencyUnit, mint_url: str | None = None
) -> str:
    raise NotImplementedError


# insert initial token state here to reduce db calls
async def create_refund_token(
    amount: int, unit: CurrencyUnit, mint_url: str | None = None
) -> str:
    wallet = await Wallet.with_db(
        mint_url, DATABASE_URL, load_all_keysets=True, unit=unit
    )
    if wallet.balance_per_minturl(unit=unit)[mint_url] < amount:
        raise ValueError("Wallet has no balance")
    if mint_url is None:
        mint_url = wallet.mint_urls[0]
    return await wallet._make_token(amount, unit=unit, mint_url=mint_url)


async def redeem_token(token: str) -> Token:
    token_obj = deserialize_token_from_string(token)
    wallet = await Wallet.with_db(
        token_obj.mint,
        DATABASE_URL,
        load_all_keysets=True,
        unit=token_obj.unit,
    )
    return await redeem_universal(wallet, token_obj)


async def delete_key_if_zero_balance(key: str) -> None:
    raise NotImplementedError


async def credit_balance(cashu_token: str, key: ApiKey, session: AsyncSession) -> int:
    raise NotImplementedError


async def check_for_refunds() -> None:
    raise NotImplementedError


async def init_wallet() -> None:
    raise NotImplementedError


async def periodic_payout() -> None:
    raise NotImplementedError


async def get_wallet_balance() -> int:
    raise NotImplementedError


# class Proof:
#     """
#     Represents an ecash bill
#     """


# def redeem_to_proofs(self, token: str) -> list[Proof]:
#     raise NotImplementedError


# class Payment:
#     """
#     Stores all cashu payment related data
#     """

#     def __init__(self, token: str) -> None:
#         self.initial_token = token
#         amount, unit, mint_url = self.parse_token(token)
#         self.amount = amount
#         self.unit = unit
#         self.mint_url = mint_url

#         self.claimed_proofs = redeem_to_proofs(token)

#     def parse_token(self, token: str) -> tuple[int, CurrencyUnit, str]:
#         raise NotImplementedError

#     def refund_full(self) -> None:
#         raise NotImplementedError

#     def refund_partial(self, amount: int) -> None:
#         raise NotImplementedError
