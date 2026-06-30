import asyncio
import time
import logging
import httpx
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

TIMEFRAMES = ["5m", "1h", "4h"]
OHLCV_LIMITS = {"5m": 100, "1h": 100, "4h": 60}


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

    async def fetch_ohlcv(self, exchange_id: str, timeframe: str = "5m", limit: int = 100) -> Optional[list]:
        exchange = self.exchanges.get(exchange_id)
        if not exchange:
            return None
        try:
            return await exchange.fetch_ohlcv(self.symbol, timeframe, limit=limit)
        except Exception as e:
            logger.warning(f"{exchange_id} OHLCV({timeframe}) error: {e}")
            return None

    async def fetch_ohlcv_multi_timeframe(self, exchange_id: str) -> dict:
        """Fetch 5m, 1h, 4h candles in parallel for multi-timeframe analysis."""
        tasks = [
            self.fetch_ohlcv(exchange_id, tf, OHLCV_LIMITS[tf])
            for tf in TIMEFRAMES
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {
            tf: (results[i] if not isinstance(results[i], Exception) else None)
            for i, tf in enumerate(TIMEFRAMES)
        }

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

    async def fetch_order_book(self, exchange_id: str, limit: int = 20) -> Optional[dict]:
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

    async def fetch_funding_rate(self) -> Optional[dict]:
        """Fetch Binance perpetual funding rate — powerful crowding indicator."""
        base = self.symbol.split("/")[0]
        perp_symbol = f"{base}/USDT:USDT"
        binance = self.exchanges.get("binance")
        if not binance:
            # Try direct HTTP if exchange not in feed
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get(
                        "https://fapi.binance.com/fapi/v1/premiumIndex",
                        params={"symbol": f"{base}USDT"},
                    )
                    data = resp.json()
                    rate = float(data.get("lastFundingRate", 0))
                    return {"rate": rate, "rate_pct": round(rate * 100, 4)}
            except Exception as e:
                logger.debug(f"Funding rate fetch error: {e}")
                return None
        try:
            # Use ccxt futures endpoint
            exchange_futures = ccxt.binance({
                "enableRateLimit": True,
                "options": {"defaultType": "future"},
            })
            funding = await exchange_futures.fetch_funding_rate(perp_symbol)
            await exchange_futures.close()
            rate = funding.get("fundingRate", 0) or 0
            return {"rate": rate, "rate_pct": round(rate * 100, 4)}
        except Exception as e:
            logger.debug(f"CCXT funding rate error: {e}")
            # Fallback to REST
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get(
                        "https://fapi.binance.com/fapi/v1/premiumIndex",
                        params={"symbol": f"{base}USDT"},
                    )
                    data = resp.json()
                    rate = float(data.get("lastFundingRate", 0))
                    return {"rate": rate, "rate_pct": round(rate * 100, 4)}
            except Exception:
                return None

    async def fetch_fear_greed(self) -> Optional[dict]:
        """Fetch Crypto Fear & Greed Index from alternative.me (free, no auth)."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get("https://api.alternative.me/fng/?limit=2")
                data = resp.json()
                entries = data.get("data", [])
                if not entries:
                    return None
                current = entries[0]
                previous = entries[1] if len(entries) > 1 else None
                score = int(current["value"])
                label = current["value_classification"]
                trend = None
                if previous:
                    delta = score - int(previous["value"])
                    trend = "rising" if delta > 0 else "falling" if delta < 0 else "stable"
                return {
                    "score": score,
                    "label": label,
                    "trend": trend,
                    "interpretation": _fear_greed_interpretation(score),
                }
        except Exception as e:
            logger.debug(f"Fear & Greed fetch error: {e}")
            return None

    async def fetch_all(self) -> dict:
        ex_ids = list(self.exchanges.keys())
        primary = ex_ids[0] if ex_ids else None

        # Parallel: tickers + order books for all exchanges
        ticker_tasks = [self.fetch_ticker(ex_id) for ex_id in ex_ids]
        ob_tasks = [self.fetch_order_book(ex_id) for ex_id in ex_ids]

        # Primary exchange: multi-timeframe OHLCV
        mtf_task = self.fetch_ohlcv_multi_timeframe(primary) if primary else asyncio.sleep(0)

        # External signals
        funding_task = self.fetch_funding_rate()
        fg_task = self.fetch_fear_greed()

        all_results = await asyncio.gather(
            *ticker_tasks, *ob_tasks, mtf_task, funding_task, fg_task,
            return_exceptions=True,
        )

        n = len(ex_ids)
        ticker_results = all_results[:n]
        ob_results = all_results[n:2 * n]
        mtf_result = all_results[2 * n]
        funding_result = all_results[2 * n + 1]
        fg_result = all_results[2 * n + 2]

        tickers = {}
        order_books = {}
        for i, ex_id in enumerate(ex_ids):
            if isinstance(ticker_results[i], dict):
                tickers[ex_id] = ticker_results[i]
            if isinstance(ob_results[i], dict):
                order_books[ex_id] = ob_results[i]

        mtf_ohlcv = mtf_result if isinstance(mtf_result, dict) else {}

        self._cache = {
            "tickers": tickers,
            "order_books": order_books,
            "ohlcv": mtf_ohlcv.get("5m"),          # backward-compat
            "ohlcv_mtf": mtf_ohlcv,                 # full multi-timeframe
            "primary_exchange": primary,
            "funding_rate": funding_result if isinstance(funding_result, dict) else None,
            "fear_greed": fg_result if isinstance(fg_result, dict) else None,
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


def _fear_greed_interpretation(score: int) -> str:
    if score <= 25:
        return "Extreme Fear — historically strong buy zone (contrarian)"
    elif score <= 45:
        return "Fear — lean bullish with caution"
    elif score <= 55:
        return "Neutral — no directional bias from sentiment"
    elif score <= 75:
        return "Greed — lean bearish, tighten take-profit targets"
    else:
        return "Extreme Greed — historically strong sell zone (contrarian)"
