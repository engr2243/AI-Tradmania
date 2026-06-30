import asyncio
import time
import logging
from typing import Dict, Optional
import ccxt.async_support as ccxt

logger = logging.getLogger(__name__)

EXCHANGE_CLASSES = {
    "binance": ccxt.binance,
    "kraken": ccxt.kraken,
    "bybit": ccxt.bybit,
    "coinbase": ccxt.coinbase,
    "kucoin": ccxt.kucoin,
}


class MarketFeed:
    def __init__(self, exchange_ids: list[str], symbol: str):
        self.symbol = symbol
        self.exchange_ids = [e for e in exchange_ids if e in EXCHANGE_CLASSES]
        self.exchanges: Dict[str, ccxt.Exchange] = {}
        self._cache: Dict[str, dict] = {}

    async def initialize(self):
        for ex_id in self.exchange_ids:
            try:
                exchange = EXCHANGE_CLASSES[ex_id]({"enableRateLimit": True})
                await exchange.load_markets()
                # Check symbol available, fallback gracefully
                if self.symbol in exchange.symbols:
                    self.exchanges[ex_id] = exchange
                    logger.info(f"Connected to {ex_id}")
                else:
                    logger.warning(f"{ex_id}: {self.symbol} not available, skipping")
                    await exchange.close()
            except Exception as e:
                logger.warning(f"Failed to initialize {ex_id}: {e}")

        if not self.exchanges:
            raise RuntimeError("No exchanges could be initialized")

    async def fetch_ohlcv(self, exchange_id: str, timeframe: str = "5m", limit: int = 50) -> Optional[list]:
        exchange = self.exchanges.get(exchange_id)
        if not exchange:
            return None
        try:
            ohlcv = await exchange.fetch_ohlcv(self.symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            logger.warning(f"{exchange_id} OHLCV error: {e}")
            return None

    async def fetch_ticker(self, exchange_id: str) -> Optional[dict]:
        exchange = self.exchanges.get(exchange_id)
        if not exchange:
            return None
        try:
            ticker = await exchange.fetch_ticker(self.symbol)
            return {
                "exchange": exchange_id,
                "symbol": self.symbol,
                "last": ticker.get("last"),
                "bid": ticker.get("bid"),
                "ask": ticker.get("ask"),
                "volume": ticker.get("baseVolume"),
                "change_pct": ticker.get("percentage"),
                "high": ticker.get("high"),
                "low": ticker.get("low"),
                "timestamp": ticker.get("timestamp", int(time.time() * 1000)),
            }
        except Exception as e:
            logger.warning(f"{exchange_id} ticker error: {e}")
            return None

    async def fetch_order_book(self, exchange_id: str, limit: int = 10) -> Optional[dict]:
        exchange = self.exchanges.get(exchange_id)
        if not exchange:
            return None
        try:
            ob = await exchange.fetch_order_book(self.symbol, limit)
            bids = ob.get("bids", [])
            asks = ob.get("asks", [])
            bid_vol = sum(b[1] for b in bids)
            ask_vol = sum(a[1] for a in asks)
            total = bid_vol + ask_vol
            imbalance = (bid_vol / total * 100) if total > 0 else 50
            return {
                "top_bid": bids[0][0] if bids else None,
                "top_ask": asks[0][0] if asks else None,
                "bid_volume": round(bid_vol, 4),
                "ask_volume": round(ask_vol, 4),
                "buy_pressure_pct": round(imbalance, 1),
                "spread": round(asks[0][0] - bids[0][0], 2) if bids and asks else None,
            }
        except Exception as e:
            logger.warning(f"{exchange_id} order book error: {e}")
            return None

    async def fetch_all(self) -> dict:
        tasks = []
        ex_ids = list(self.exchanges.keys())

        for ex_id in ex_ids:
            tasks.append(self.fetch_ticker(ex_id))
            tasks.append(self.fetch_order_book(ex_id))

        # Primary exchange gets OHLCV
        primary = ex_ids[0] if ex_ids else None
        ohlcv_task = self.fetch_ohlcv(primary) if primary else asyncio.sleep(0)

        results = await asyncio.gather(*tasks, ohlcv_task, return_exceptions=True)

        tickers = {}
        order_books = {}
        for i, ex_id in enumerate(ex_ids):
            ticker = results[i * 2]
            ob = results[i * 2 + 1]
            if isinstance(ticker, dict):
                tickers[ex_id] = ticker
            if isinstance(ob, dict):
                order_books[ex_id] = ob

        ohlcv = results[-1] if not isinstance(results[-1], Exception) else None

        self._cache = {
            "tickers": tickers,
            "order_books": order_books,
            "ohlcv": ohlcv,
            "primary_exchange": primary,
            "timestamp": int(time.time() * 1000),
        }
        return self._cache

    def get_cached(self) -> dict:
        return self._cache

    async def close(self):
        for exchange in self.exchanges.values():
            try:
                await exchange.close()
            except Exception:
                pass
