import os
import httpx
import asyncio

# artifical spread to cover conversion fees
EXCHANGE_FEE = os.environ.get("EXCHANGE_FEE", 1.005)  # 0.5% default


async def kraken_btc_usd(client: httpx.AsyncClient) -> int:
    api = "https://api.kraken.com/0/public/Ticker?pair=XBTUSD"
    return int(float((await client.get(api)).json()["result"]["XXBTZUSD"]["c"][0]))


async def coinbase_btc_usd(client: httpx.AsyncClient) -> int:
    api = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
    return int(float((await client.get(api)).json()["data"]["amount"]))


async def binance_btc_usdt(client: httpx.AsyncClient) -> int:
    api = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
    return int(float((await client.get(api)).json()["price"]))


async def btc_usd_ask_price() -> int:
    async with httpx.AsyncClient() as client:
        return int(
            max(
                await asyncio.gather(
                    kraken_btc_usd(client),
                    coinbase_btc_usd(client),
                    binance_btc_usdt(client),
                )
            )
            * EXCHANGE_FEE
        )
