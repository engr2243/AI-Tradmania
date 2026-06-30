import logging
import time
import ccxt.async_support as ccxt

from config import BINANCE_API_KEY, BINANCE_SECRET

logger = logging.getLogger(__name__)


class BinanceLiveExecutor:
    """
    Places real orders on Binance using authenticated CCXT.
    Uses market orders for guaranteed fills — no slippage risk from missed limits.
    """

    def __init__(self):
        self.exchange: ccxt.binance = ccxt.binance({
            "apiKey": BINANCE_API_KEY,
            "secret": BINANCE_SECRET,
            "enableRateLimit": True,
            "options": {
                "defaultType": "spot",
                "recvWindow": 10000,
            },
        })
        self._initialized = False

    async def initialize(self):
        await self.exchange.load_markets()
        # Verify credentials work by fetching balance
        balance = await self.exchange.fetch_balance()
        usdt = balance["USDT"]["free"]
        logger.info(f"Binance live executor ready | USDT balance: ${usdt:,.2f}")
        self._initialized = True
        return usdt

    async def fetch_balances(self, symbol: str) -> dict:
        """Fetch real account balances from Binance."""
        balance = await self.exchange.fetch_balance()
        base = symbol.split("/")[0]   # e.g. BTC
        quote = symbol.split("/")[1]  # e.g. USDT
        return {
            "usdt_free": balance.get(quote, {}).get("free", 0),
            "usdt_total": balance.get(quote, {}).get("total", 0),
            "base_free": balance.get(base, {}).get("free", 0),
            "base_total": balance.get(base, {}).get("total", 0),
        }

    async def buy(self, symbol: str, spend_usdt: float) -> dict:
        """
        Place a market BUY order.
        spend_usdt: amount of USDT to spend (bot calculates qty from current price).
        Returns normalized trade dict.
        """
        if not self._initialized:
            raise RuntimeError("Executor not initialized")

        # Fetch current ask price to calculate quantity
        ticker = await self.exchange.fetch_ticker(symbol)
        ask_price = ticker["ask"]
        qty = spend_usdt / ask_price

        # Apply exchange minimum notional / lot size filters
        market = self.exchange.market(symbol)
        qty = self.exchange.amount_to_precision(symbol, qty)

        logger.info(f"LIVE BUY: {qty} {symbol} @ market (~${ask_price:,.2f}) | Cost: ${spend_usdt:.2f}")

        order = await self.exchange.create_order(
            symbol=symbol,
            type="market",
            side="buy",
            amount=float(qty),
        )

        return self._normalize_order(order, "buy")

    async def sell(self, symbol: str, qty: float) -> dict:
        """
        Place a market SELL order for the given quantity.
        Returns normalized trade dict.
        """
        if not self._initialized:
            raise RuntimeError("Executor not initialized")

        qty = self.exchange.amount_to_precision(symbol, qty)

        logger.info(f"LIVE SELL: {qty} {symbol} @ market")

        order = await self.exchange.create_order(
            symbol=symbol,
            type="market",
            side="sell",
            amount=float(qty),
        )

        return self._normalize_order(order, "sell")

    def _normalize_order(self, order: dict, side: str) -> dict:
        filled = order.get("filled") or order.get("amount", 0)
        cost = order.get("cost") or 0
        price = order.get("average") or order.get("price") or (cost / filled if filled else 0)
        fee = 0
        if order.get("fee"):
            fee = order["fee"].get("cost", 0)

        return {
            "id": len([]) + 1,   # will be overwritten by portfolio
            "exchange_order_id": order.get("id"),
            "side": side,
            "price": round(float(price), 2),
            "amount": round(float(filled), 8),
            "cost": round(float(cost), 4),
            "fee": round(float(fee), 6),
            "pnl": 0,
            "mode": "live",
            "timestamp": order.get("timestamp") or int(time.time() * 1000),
            "status": order.get("status", "closed"),
        }

    async def close(self):
        await self.exchange.close()
