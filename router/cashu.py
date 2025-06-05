import os
import asyncio
import time

from sixty_nuts import Wallet
from sqlmodel import select, func, col
from .db import ApiKey, AsyncSession, get_session


RECEIVE_LN_ADDRESS = os.environ["RECEIVE_LN_ADDRESS"]
MINT = os.environ.get("MINT", "https://mint.minibits.cash/Bitcoin")
MINIMUM_PAYOUT = int(os.environ.get("MINIMUM_PAYOUT", 100))
REFUND_PROCESSING_INTERVAL = int(os.environ.get("REFUND_PROCESSING_INTERVAL", 3600))
DEV_LN_ADDRESS = "routstr@minibits.cash"
DEVS_DONATION_RATE = float(os.environ.get("DEVS_DONATION_RATE", 0.021))  # 2.1%
NSEC = os.environ["NSEC"]  # Nostr private key for the wallet


async def pay_out() -> None:
    """
    Calculates the pay-out amount based on the spent balance, profit, and donation rate.
    """
    try:
        from .db import create_session

        async with create_session() as session:
            balance = (
                await session.exec(
                    select(func.sum(col(ApiKey.balance))).where(ApiKey.balance > 0)
                )
            ).one()
            if balance is None or balance == 0:
                # No balance to pay out - this is OK, not an error
                return

            user_balance_sats = balance // 1000
            async with Wallet(nsec=NSEC, mint_urls=[MINT]) as wallet:
                state = await wallet.fetch_wallet_state()
                wallet_balance_sats = state.balance

            # Handle edge cases more gracefully
            if wallet_balance_sats < user_balance_sats:
                print(
                    f"Warning: Wallet balance ({wallet_balance_sats} sats) is less than user balance ({user_balance_sats} sats). Skipping payout."
                )
                return

            if (revenue := wallet_balance_sats - user_balance_sats) <= MINIMUM_PAYOUT:
                # Not enough revenue yet - this is OK
                return

            devs_donation = int(revenue * DEVS_DONATION_RATE)
            owners_draw = revenue - devs_donation

            # Send payouts
            async with Wallet(nsec=NSEC, mint_urls=[MINT]) as wallet:
                await wallet.send_to_lnurl(RECEIVE_LN_ADDRESS, owners_draw)
                await wallet.send_to_lnurl(DEV_LN_ADDRESS, devs_donation)

    except Exception as e:
        # Log the error but don't crash - payouts can be retried later
        print(f"Error in pay_out: {e}")


async def credit_balance(cashu_token: str, key: ApiKey, session: AsyncSession) -> int:
    async with Wallet(nsec=NSEC, mint_urls=[MINT]) as wallet:
        state_before = await wallet.fetch_wallet_state()
        await wallet.redeem(cashu_token)
        state_after = await wallet.fetch_wallet_state()
        amount = (state_after.balance - state_before.balance) * 1000
        key.balance += amount
        session.add(key)
        await session.commit()
        return amount


async def check_for_refunds() -> None:
    """
    Periodically checks for API keys that are eligible for refunds and processes them.

    Raises:
        Exception: If an error occurs during the refund check process.
    """
    raise Exception("TODO migrate to sixty-nuts")
    # Setting REFUND_PROCESSING_INTERVAL to 0 disables it
    if REFUND_PROCESSING_INTERVAL == 0:
        print("Automatic refund processing is disabled.")
        return

    while True:
        try:
            async for session in get_session():
                result = await session.exec(select(ApiKey))
                keys = result.all()
                current_time = int(time.time())
                for key in keys:
                    if (
                        key.balance > 0
                        and key.refund_address
                        and key.key_expiry_time
                        and key.key_expiry_time < current_time
                    ):
                        print(
                            f"       DEBUG   Refunding key {key.hashed_key[:3] + '[...]' + key.hashed_key[-3:]}, Current Time: {current_time}, Expirary Time: {key.key_expiry_time}",
                            flush=True,
                        )
                        await refund_balance(key.balance, key, session)

            # Sleep for the specified interval before checking again
            await asyncio.sleep(REFUND_PROCESSING_INTERVAL)
        except Exception as e:
            print(f"Error during refund check: {e}")


async def refund_balance(amount: int, key: ApiKey, session: AsyncSession) -> int:
    async with Wallet(nsec=NSEC, mint_urls=[MINT]) as wallet:
        if key.balance < amount:
            raise ValueError("Insufficient balance.")
        if amount <= 0:
            amount = key.balance

        key.balance -= amount
        session.add(key)
        await session.commit()

        if key.refund_address is None:
            raise ValueError("Refund address not set.")

        return await wallet.send_to_lnurl(
            key.refund_address,
            amount=amount,
        )


async def redeem(cashu_token: str, lnurl: str) -> int:
    async with Wallet(nsec=NSEC, mint_urls=[MINT]) as wallet:
        state_before = await wallet.fetch_wallet_state()
        await wallet.redeem(cashu_token)
        state_after = await wallet.fetch_wallet_state()
        amount = state_after.balance - state_before.balance
        await wallet.send_to_lnurl(lnurl, amount=amount)
        return amount
