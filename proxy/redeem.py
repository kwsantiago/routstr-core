import httpx
import os

from cashu.core.base import Token  # type: ignore
from cashu.wallet.wallet import Wallet  # type: ignore
from cashu.core.settings import settings  # type: ignore
from cashu.wallet.helpers import deserialize_token_from_string, receive  # type: ignore


async def _initialize_wallet(mint_url: str) -> Wallet:
    """Initializes and loads a Cashu wallet."""
    wallet = await Wallet.with_db(
        mint_url,
        db=os.path.join(settings.cashu_dir, "temp"),
        load_all_keysets=True,
    )
    await wallet.load_mint_info()
    await wallet.load_proofs(reload=True)
    return wallet


async def _handle_token_receive(wallet: Wallet, token_obj: Token) -> int:
    """Receives a token and returns the amount received."""
    initial_balance = wallet.available_balance
    await receive(wallet, token_obj)
    await wallet.load_proofs(reload=True)
    final_balance = wallet.available_balance
    amount_received = final_balance - initial_balance

    if amount_received <= 0:
        raise ValueError("Token contained no value.")
    return amount_received


async def _get_lnurl_invoice(callback_url: str, amount_sat: int) -> tuple[str, dict]:
    """Requests an invoice from the LNURL callback URL."""
    amount_msats = amount_sat * 1000
    async with httpx.AsyncClient() as client:
        response = await client.get(
            callback_url,
            params={"amount": amount_msats},
            follow_redirects=True,
        )
        response.raise_for_status()  # Raise exception for non-2xx status codes
    invoice_data = response.json()
    if "pr" not in invoice_data:
        raise ValueError(f"Invalid LNURL invoice response: {invoice_data}")
    return invoice_data["pr"], invoice_data


async def _pay_invoice_with_cashu(
    wallet: Wallet, bolt11_invoice: str, amount_to_send_sat: int
) -> int:
    """Pays a BOLT11 invoice using Cashu proofs via melt."""

    quote = await wallet.melt_quote(bolt11_invoice, amount_to_send_sat)

    proofs_to_melt, _ = await wallet.select_to_send(
        wallet.proofs, quote.amount + quote.fee_reserve
    )

    _ = await wallet.melt(
        proofs_to_melt, bolt11_invoice, quote.fee_reserve, quote.quote
    )

    return quote.amount


async def redeem(cashu_token: str, lnurl: str) -> int:
    """
    Redeems a Cashu token and sends the amount to an LNURL address.

    Args:
        cashu_token: The Cashu token string (starting with "cashuA...").
        lnurl: The LNURL string (can be bech32, user@host, or direct URL).

    Returns:
        The amount in satoshis that was successfully sent.

    Raises:
        Exception: If any step of the process fails (token receive, LNURL fetch, invoice payment).
    """
    token_obj: Token = deserialize_token_from_string(cashu_token)
    wallet: Wallet = await _initialize_wallet(token_obj.mint)

    amount_received = await _handle_token_receive(wallet, token_obj)

    # if USE_BALANCE_ON_INVALID_TOKEN:
    #     amount_received = wallet.available_balance

    callback_url, min_sendable, max_sendable = await get_lnurl_data(lnurl)

    if not (min_sendable <= amount_received * 1000 <= max_sendable):
        raise ValueError(
            f"Amount {amount_received} sat is outside LNURL limits "
            f"({min_sendable / 1000} - {max_sendable / 1000} sat)."
        )
    # subtract estimated fees
    amount_to_send = amount_received - int(max(2, amount_received * 0.01))

    # Note: We pass amount_received directly. The actual amount paid might be adjusted
    # slightly by the melt quote based on the invoice details.
    bolt11_invoice, _ = await _get_lnurl_invoice(callback_url, amount_to_send)

    amount_paid = await _pay_invoice_with_cashu(wallet, bolt11_invoice, amount_to_send)

    return amount_paid


async def get_lnurl_data(lnurl: str) -> tuple[str, int, int]:
    """
    Fetches LNURL payRequest data (callback URL, min/max sendable amounts).

    Handles lightning:, user@host, bech32 lnurl, and direct HTTPS URL formats.
    """
    url: str
    if lnurl.startswith("lightning:"):
        lnurl = lnurl[10:]

    if "@" in lnurl and len(lnurl.split("@")) == 2:
        user, host = lnurl.split("@")
        url = f"https://{host}/.well-known/lnurlp/{user}"
    elif lnurl.lower().startswith("lnurl"):
        try:
            # Optional import for environments where bech32 might not be present initially
            from bech32 import bech32_decode, convertbits

            hrp, data = bech32_decode(lnurl)
            if data is None:
                raise ValueError("Invalid bech32 data in LNURL")
            decoded_data = convertbits(data, 5, 8, False)
            if decoded_data is None:
                raise ValueError("Failed to convert LNURL bits")
            url = bytes(decoded_data).decode("utf-8")
        except ImportError:
            raise ImportError("bech32 library is required for LNURL bech32 decoding.")
        except Exception as e:
            raise ValueError(f"Failed to decode LNURL: {e}") from e
    else:
        # Assume it's a direct URL
        if not lnurl.startswith("https://"):
            # Basic check, could be improved
            raise ValueError("Direct LNURL must use HTTPS")
        url = lnurl

    async with httpx.AsyncClient() as client:
        response = await client.get(url, follow_redirects=True, timeout=10)
        response.raise_for_status()  # Raises HTTPStatusError for 4xx/5xx
        lnurl_data: dict = response.json()

    if lnurl_data.get("tag") != "payRequest" or not isinstance(
        lnurl_data.get("callback"), str
    ):
        raise ValueError(f"Invalid LNURL payRequest data: {lnurl_data}")

    callback_url: str = lnurl_data["callback"]
    # LNURL spec defaults (in millisatoshis)
    min_sendable: int = lnurl_data.get("minSendable", 1000)
    max_sendable: int = lnurl_data.get("maxSendable", 1000000000)  # Default 1000 BTC

    return callback_url, min_sendable, max_sendable


if __name__ == "__main__":
    import asyncio

    # Example usage: Replace with your actual LNURL and Token
    lnurl = "user@walletofsatoshi.com"  # Replace
    # A potentially spent token for testing fallback logic
    cashu_token = "cashuBpGF0gaJhaUg..."

    # Example: Set USE_BALANCE_ON_INVALID_TOKEN = False to test non-fallback behavior
    # USE_BALANCE_ON_INVALID_TOKEN = True

    async def main() -> None:
        # Removed try-except block, script will crash on error
        print(f"Attempting to redeem token and pay LNURL: {lnurl}")
        amount_sent = await redeem(cashu_token, lnurl)
        print(f"✅ Successfully sent {amount_sent} sat.")

    # Removed try-except block for KeyboardInterrupt
    asyncio.run(main())
