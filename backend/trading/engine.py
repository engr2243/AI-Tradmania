import asyncio
import logging
import time
from typing import Optional, Callable

from config import (
    TARGET_SYMBOL,
    TRADING_MODE,
    INITIAL_BALANCE,
    ANALYSIS_INTERVAL_SECONDS,
    EXCHANGES,
    BINANCE_API_KEY,
)
from data.market_feed import MarketFeed
from data.indicators import compute_indicators, compute_multi_timeframe, build_signal_scorecard
from ai.prompt_builder import build_trading_prompt
from ai.claude_engine import analyze_market
from trading.portfolio import Portfolio
from trading.risk import RiskManager
from trading.live_executor import BinanceLiveExecutor

logger = logging.getLogger(__name__)


class TradingEngine:
    def __init__(self, on_update: Optional[Callable] = None):
        self.symbol = TARGET_SYMBOL
        self.mode = TRADING_MODE
        self.feed = MarketFeed(EXCHANGES, self.symbol)
        self.portfolio = Portfolio(INITIAL_BALANCE, self.symbol)
        self.risk = RiskManager()
        self.on_update = on_update

        self.live_executor: Optional[BinanceLiveExecutor] = None
        self.running = False
        self.last_decision: dict = {}
        self.last_market_data: dict = {}
        self.last_indicators: dict = {}
        self.last_mtf: dict = {}
        self.last_scorecard: dict = {}
        self.cycle_count = 0
        self.errors: list = []
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        logger.info(f"Initializing market feeds for {self.symbol}...")
        await self.feed.initialize()

        if self.mode == "live":
            if not BINANCE_API_KEY:
                raise RuntimeError("BINANCE_API_KEY not set — cannot start in live mode")
            self.live_executor = BinanceLiveExecutor()
            real_usdt = await self.live_executor.initialize()
            balances = await self.live_executor.fetch_balances(self.symbol)
            self.portfolio.balance_usdt = balances["usdt_free"]
            self.portfolio.holdings = balances["base_free"]
            logger.info(f"Live mode: synced Binance balance — ${real_usdt:,.2f} USDT")

        self.running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Engine started | Mode: {self.mode} | Symbol: {self.symbol}")

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
        await self.feed.close()
        if self.live_executor:
            await self.live_executor.close()
        logger.info("Trading engine stopped")

    async def _loop(self):
        while self.running:
            try:
                await self._cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cycle error: {e}", exc_info=True)
                self.errors.append({"time": int(time.time()), "error": str(e)})
            await asyncio.sleep(ANALYSIS_INTERVAL_SECONDS)

    async def _cycle(self):
        self.cycle_count += 1
        logger.info(f"--- Cycle {self.cycle_count} ---")

        # 1. Fetch all market data (tickers, order books, multi-TF OHLCV, F&G, funding)
        market_data = await self.feed.fetch_all()
        self.last_market_data = market_data

        tickers = market_data.get("tickers", {})
        primary_ticker = next(iter(tickers.values()), {})
        current_price = primary_ticker.get("last")
        if not current_price:
            logger.warning("No price data, skipping cycle")
            return

        # 2. Compute indicators — primary timeframe + multi-timeframe
        ohlcv_5m = market_data.get("ohlcv") or []
        ohlcv_mtf = market_data.get("ohlcv_mtf") or {}
        indicators = compute_indicators(ohlcv_5m)
        mtf = compute_multi_timeframe(ohlcv_mtf)
        self.last_indicators = indicators
        self.last_mtf = mtf

        # 3. Build signal scorecard
        scorecard = build_signal_scorecard(
            ind=indicators,
            mtf_alignment=mtf.get("alignment", {}),
            fear_greed=market_data.get("fear_greed"),
            funding_rate=market_data.get("funding_rate"),
        )
        self.last_scorecard = scorecard

        # 4. Check stop-loss / take-profit (bypasses Claude)
        portfolio_state = self.portfolio.get_state(current_price)
        sl_tp = self.risk.check_stop_loss_take_profit(portfolio_state, current_price)

        executed_trade = None

        if sl_tp.get("trigger") == "SELL":
            forced_decision = {
                "action": "SELL",
                "confidence": 1.0,
                "amount_pct": sl_tp.get("amount_pct", 100),
                "reason": sl_tp["reason"],
                "key_signals": ["stop_loss_take_profit"],
                "risk_level": "HIGH",
            }
            self.last_decision = forced_decision
            executed_trade = await self._execute_trade(forced_decision, current_price)
            if executed_trade:
                pnl = executed_trade.get("pnl", 0)
                self.risk.record_trade_outcome(pnl)
                self.portfolio.resolve_last_decision(pnl)
        else:
            # 5. Build prompt with all intelligence layers
            prompt = build_trading_prompt(
                symbol=self.symbol,
                tickers=tickers,
                order_books=market_data.get("order_books", {}),
                indicators=indicators,
                mtf=mtf,
                portfolio=portfolio_state,
                recent_trades=self.portfolio.get_recent_trades(3),
                decision_memory=self.portfolio.decision_memory,
                fear_greed=market_data.get("fear_greed"),
                funding_rate=market_data.get("funding_rate"),
                scorecard=scorecard,
            )

            # 6. Call Claude (thread pool — non-blocking)
            loop = asyncio.get_event_loop()
            decision = await loop.run_in_executor(None, analyze_market, prompt)
            self.last_decision = decision

            # 7. Record decision in memory
            self.portfolio.record_decision(decision, current_price)

            # 8. Execute if action taken
            if decision["action"] in ("BUY", "SELL"):
                executed_trade = await self._execute_trade(decision, current_price)
                if executed_trade:
                    pnl = executed_trade.get("pnl", 0)
                    self.risk.record_trade_outcome(pnl)
                    if decision["action"] == "SELL":
                        self.portfolio.resolve_last_decision(pnl)

        # 9. Broadcast full state
        state = self.get_full_state(current_price, indicators, mtf, scorecard, executed_trade)
        if self.on_update:
            await self.on_update(state)

    # ── Trade execution routing ───────────────────────────────────────────────

    async def _execute_trade(self, decision: dict, price: float) -> Optional[dict]:
        if decision["action"] == "BUY":
            return (await self._live_buy(decision, price)) if self.mode == "live" else self._execute_buy(decision, price)
        if decision["action"] == "SELL":
            return (await self._live_sell(decision, price)) if self.mode == "live" else self._execute_sell(decision, price)
        return None

    def _execute_buy(self, decision: dict, price: float) -> Optional[dict]:
        portfolio_state = self.portfolio.get_state(price)
        ok, spend, msg = self.risk.validate_buy(decision, portfolio_state, price)
        if not ok:
            logger.info(f"BUY blocked: {msg}")
            return None
        trade = self.portfolio.apply_buy(price, spend)
        if trade:
            trade["mode"] = "paper"
            trade["risk_msg"] = msg
        return trade

    def _execute_sell(self, decision: dict, price: float) -> Optional[dict]:
        portfolio_state = self.portfolio.get_state(price)
        ok, amount_pct, msg = self.risk.validate_sell(decision, portfolio_state, price)
        if not ok:
            logger.info(f"SELL blocked: {msg}")
            return None
        trade = self.portfolio.apply_sell(price, amount_pct)
        if trade:
            trade["mode"] = "paper"
            trade["risk_msg"] = msg
        return trade

    async def _live_buy(self, decision: dict, price: float) -> Optional[dict]:
        portfolio_state = self.portfolio.get_state(price)
        ok, spend, msg = self.risk.validate_buy(decision, portfolio_state, price)
        if not ok:
            logger.info(f"BUY blocked: {msg}")
            return None
        try:
            order = await self.live_executor.buy(self.symbol, spend)
        except Exception as e:
            logger.error(f"Live BUY failed: {e}")
            self.errors.append({"time": int(time.time()), "error": f"Live BUY: {e}"})
            return None
        filled_qty = order["amount"]
        filled_price = order["price"]
        if self.portfolio.holdings == 0:
            self.portfolio.avg_buy_price = filled_price
        else:
            total_cost = self.portfolio.avg_buy_price * self.portfolio.holdings + filled_price * filled_qty
            self.portfolio.avg_buy_price = total_cost / (self.portfolio.holdings + filled_qty)
        await self._sync_live_balances()
        trade = self.portfolio.record_live_trade(order, pnl=0)
        trade["risk_msg"] = msg
        return trade

    async def _live_sell(self, decision: dict, price: float) -> Optional[dict]:
        portfolio_state = self.portfolio.get_state(price)
        ok, amount_pct, msg = self.risk.validate_sell(decision, portfolio_state, price)
        if not ok:
            logger.info(f"SELL blocked: {msg}")
            return None
        qty_to_sell = self.portfolio.holdings * (amount_pct / 100)
        try:
            order = await self.live_executor.sell(self.symbol, qty_to_sell)
        except Exception as e:
            logger.error(f"Live SELL failed: {e}")
            self.errors.append({"time": int(time.time()), "error": f"Live SELL: {e}"})
            return None
        avg_buy = self.portfolio.avg_buy_price or order["price"]
        pnl = (order["price"] - avg_buy) * order["amount"] - order["fee"]
        await self._sync_live_balances()
        trade = self.portfolio.record_live_trade(order, pnl=pnl)
        trade["risk_msg"] = msg
        return trade

    async def _sync_live_balances(self):
        try:
            balances = await self.live_executor.fetch_balances(self.symbol)
            tickers = self.last_market_data.get("tickers", {})
            primary = next(iter(tickers.values()), {})
            price = primary.get("last") or 0
            self.portfolio.sync_from_exchange(balances, price)
        except Exception as e:
            logger.warning(f"Balance sync failed: {e}")

    # ── State snapshot ────────────────────────────────────────────────────────

    def get_full_state(
        self,
        current_price: Optional[float] = None,
        indicators: dict = None,
        mtf: dict = None,
        scorecard: dict = None,
        last_trade: dict = None,
    ) -> dict:
        if current_price is None:
            tickers = self.last_market_data.get("tickers", {})
            current_price = next(iter(tickers.values()), {}).get("last")

        portfolio_state = self.portfolio.get_state(current_price)

        return {
            "symbol": self.symbol,
            "mode": self.mode,
            "running": self.running,
            "cycle": self.cycle_count,
            "timestamp": int(time.time() * 1000),
            "current_price": current_price,
            "tickers": self.last_market_data.get("tickers", {}),
            "order_books": self.last_market_data.get("order_books", {}),
            "ohlcv": self.last_market_data.get("ohlcv", []),
            "indicators": indicators or self.last_indicators,
            "mtf": mtf or self.last_mtf,
            "scorecard": scorecard or self.last_scorecard,
            "fear_greed": self.last_market_data.get("fear_greed"),
            "funding_rate": self.last_market_data.get("funding_rate"),
            "portfolio": portfolio_state,
            "decision": self.last_decision,
            "last_trade": last_trade,
            "recent_trades": self.portfolio.get_recent_trades(20),
            "decision_memory": self.portfolio.decision_memory,
            "signal_performance": self.portfolio.get_signal_performance(),
            "risk": self.risk.get_status(),
            "risk_halted": self.risk.halt,
            "halt_reason": self.risk.halt_reason,
            "errors": self.errors[-5:],
        }

    def set_mode(self, mode: str):
        if mode in ("paper", "live"):
            self.mode = mode

    def set_symbol(self, symbol: str):
        self.symbol = symbol
        self.feed.symbol = symbol
