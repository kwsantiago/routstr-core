import os
from typing import Literal

from cashu.wallet.helpers import deserialize_token_from_string, receive, send
from cashu.wallet.wallet import Wallet

from .db import ApiKey, AsyncSession

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


CurrencyUnit = Literal["sat", "msat"]

PRIMARY_MINT_URL = os.environ["CASHU_MINTS"].split(",")[0]


async def get_balance(unit: CurrencyUnit) -> int:
    wallet = await Wallet.with_db(
        PRIMARY_MINT_URL,
        # DATABASE_URL,
        db=".wallet",
        load_all_keysets=True,
        unit=unit,
    )
    wallet.load_proofs()
    return wallet.available_balance.amount


async def recieve_token(
    token: str,
) -> tuple[int, CurrencyUnit, str]:  # amount, unit, mint_url
    # trusted_mints = os.environ["CASHU_MINTS"].split(",")
    token_obj = deserialize_token_from_string(token)
    wallet = await Wallet.with_db(
        token_obj.mint,
        db=".wallet",
        load_all_keysets=True,
        unit=token_obj.unit,
    )
    await receive(wallet, token_obj)
    return token_obj.amount, token_obj.unit, token_obj.mint


async def send_token(
    amount: int, unit: CurrencyUnit, mint_url: str | None = None
) -> str:
    wallet = await Wallet.with_db(
        mint_url or PRIMARY_MINT_URL,
        db=".wallet",
        load_all_keysets=True,
        unit=unit,
    )
    balance, token = await send(wallet, amount=amount, lock="", legacy=False)
    return token


# insert initial token state here to reduce db calls
# async def create_refund_token(
#     amount: int, unit: CurrencyUnit, mint_url: str | None = None
# ) -> str:
#     wallet = await Wallet.with_db(
#         mint_url, DATABASE_URL, load_all_keysets=True, unit=unit
#     )
#     if wallet.balance_per_minturl(unit=unit)[mint_url] < amount:
#         raise ValueError("Wallet has no balance")
#     if mint_url is None:
#         mint_url = wallet.mint_urls[0]
#     return await wallet._make_token(amount, unit=unit, mint_url=mint_url)


# async def redeem_token(token: str) -> Token:
#     token_obj = deserialize_token_from_string(token)
#     wallet = await Wallet.with_db(
#         token_obj.mint,
#         DATABASE_URL,
#         load_all_keysets=True,
#         unit=token_obj.unit,
#     )
#     return await redeem_universal(wallet, token_obj)


async def credit_balance(cashu_token: str, key: ApiKey, session: AsyncSession) -> int:
    raise NotImplementedError


async def send_to_lnurl(amount: int, unit: CurrencyUnit, lnurl: str) -> dict[str, int]:
    raise NotImplementedError


async def check_for_refunds() -> None:
    print("check_for_refunds, temp not implemented")


async def init_wallet() -> None:
    balance = await get_balance("sat")
    print(f"init_wallet, balance: {balance}")


async def periodic_payout() -> None:
    print("periodic_payout, temp not implemented")


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
