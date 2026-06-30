import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class Portfolio:
    def __init__(self, initial_balance: float, symbol: str):
        self.symbol = symbol
        self.base_currency = symbol.split("/")[0]
        self.quote_currency = symbol.split("/")[1]

        self.balance_usdt = initial_balance
        self.initial_balance = initial_balance
        self.holdings = 0.0
        self.avg_buy_price: Optional[float] = None

        self.realized_pnl = 0.0
        self.trade_history: list = []
        self.session_start_value = initial_balance
        self.day_start_value = initial_balance
        self.day_start_time = time.time()

        # Decision memory: stores each Claude decision + eventual outcome
        self.decision_memory: list = []

        # Performance tracking per signal
        self.signal_stats: dict = {}

    # ── State ────────────────────────────────────────────────────────────────

    def get_state(self, current_price: Optional[float] = None) -> dict:
        holdings_value = (self.holdings * current_price) if current_price and self.holdings else 0
        total_value = self.balance_usdt + holdings_value

        unrealized_pnl = 0.0
        if self.holdings > 0 and self.avg_buy_price and current_price:
            unrealized_pnl = (current_price - self.avg_buy_price) * self.holdings

        if time.time() - self.day_start_time > 86400:
            self.day_start_value = total_value
            self.day_start_time = time.time()

        daily_drawdown_pct = 0.0
        if self.day_start_value > 0:
            daily_drawdown_pct = max(0, (self.day_start_value - total_value) / self.day_start_value * 100)

        wins = [t for t in self.trade_history if t.get("pnl", 0) > 0]
        losses = [t for t in self.trade_history if t.get("pnl", 0) < 0]
        win_rate = len(wins) / len(self.trade_history) * 100 if self.trade_history else 0

        return {
            "balance_usdt": round(self.balance_usdt, 4),
            "holdings": round(self.holdings, 8),
            "holdings_value": round(holdings_value, 4),
            "total_value": round(total_value, 4),
            "avg_buy_price": round(self.avg_buy_price, 2) if self.avg_buy_price else None,
            "unrealized_pnl": round(unrealized_pnl, 4),
            "realized_pnl": round(self.realized_pnl, 4),
            "total_pnl": round(unrealized_pnl + self.realized_pnl, 4),
            "total_pnl_pct": round((unrealized_pnl + self.realized_pnl) / self.initial_balance * 100, 2),
            "daily_drawdown_pct": round(daily_drawdown_pct, 2),
            "trade_count": len(self.trade_history),
            "win_rate": round(win_rate, 1),
            "wins": len(wins),
            "losses": len(losses),
        }

    # ── Paper trade execution ─────────────────────────────────────────────────

    def apply_buy(self, price: float, amount_usdt: float, fee_pct: float = 0.001) -> Optional[dict]:
        if amount_usdt > self.balance_usdt:
            amount_usdt = self.balance_usdt
        if amount_usdt <= 0:
            return None

        fee = amount_usdt * fee_pct
        net_usdt = amount_usdt - fee
        qty = net_usdt / price

        if self.holdings == 0:
            self.avg_buy_price = price
        else:
            total_cost = self.avg_buy_price * self.holdings + price * qty
            self.avg_buy_price = total_cost / (self.holdings + qty)

        self.holdings += qty
        self.balance_usdt -= amount_usdt

        trade = {
            "id": len(self.trade_history) + 1,
            "side": "buy",
            "price": round(price, 2),
            "amount": round(qty, 8),
            "cost": round(amount_usdt, 4),
            "fee": round(fee, 4),
            "pnl": 0,
            "timestamp": int(time.time() * 1000),
        }
        self.trade_history.append(trade)
        logger.info(f"BUY {qty:.6f} {self.base_currency} @ ${price:,.2f} | Cost: ${amount_usdt:.2f}")
        return trade

    def apply_sell(self, price: float, amount_pct: float = 100, fee_pct: float = 0.001) -> Optional[dict]:
        if self.holdings <= 0:
            return None

        qty = self.holdings * (amount_pct / 100)
        gross = qty * price
        fee = gross * fee_pct
        net = gross - fee

        pnl = 0.0
        if self.avg_buy_price:
            pnl = (price - self.avg_buy_price) * qty - fee

        self.holdings -= qty
        self.balance_usdt += net
        self.realized_pnl += pnl

        if self.holdings < 1e-8:
            self.holdings = 0
            self.avg_buy_price = None

        trade = {
            "id": len(self.trade_history) + 1,
            "side": "sell",
            "price": round(price, 2),
            "amount": round(qty, 8),
            "cost": round(gross, 4),
            "fee": round(fee, 4),
            "pnl": round(pnl, 4),
            "timestamp": int(time.time() * 1000),
        }
        self.trade_history.append(trade)
        logger.info(f"SELL {qty:.6f} {self.base_currency} @ ${price:,.2f} | P&L: ${pnl:+.2f}")
        return trade

    # ── Live trade support ───────────────────────────────────────────────────

    def sync_from_exchange(self, balances: dict, current_price: float):
        self.balance_usdt = balances["usdt_free"]
        self.holdings = balances["base_free"]
        if self.holdings > 0 and self.avg_buy_price is None:
            self.avg_buy_price = current_price
        logger.info(f"Portfolio synced | USDT: ${self.balance_usdt:.2f} | Holdings: {self.holdings:.8f}")

    def record_live_trade(self, order: dict, pnl: float = 0) -> dict:
        trade = {**order, "id": len(self.trade_history) + 1, "pnl": round(pnl, 4)}
        self.trade_history.append(trade)
        self.realized_pnl += pnl
        return trade

    # ── Decision memory ──────────────────────────────────────────────────────

    def record_decision(self, decision: dict, current_price: float):
        """Record every Claude decision for memory injection next cycle."""
        entry = {
            "action": decision.get("action"),
            "confidence": decision.get("confidence", 0),
            "key_signals": decision.get("key_signals", []),
            "rr_ratio": decision.get("rr_ratio"),
            "price_at": round(current_price, 2),
            "timestamp": int(time.time() * 1000),
            "outcome": "pending",
            "pnl": None,
        }
        self.decision_memory.append(entry)
        # Keep last 10
        self.decision_memory = self.decision_memory[-10:]

    def resolve_last_decision(self, pnl: float):
        """After a trade closes, mark the last BUY/SELL decision with its outcome."""
        for d in reversed(self.decision_memory):
            if d["outcome"] == "pending" and d["action"] in ("BUY", "SELL"):
                d["pnl"] = round(pnl, 4)
                d["outcome"] = "profit" if pnl > 0 else "loss"
                # Update signal stats
                for sig in d.get("key_signals", []):
                    if sig not in self.signal_stats:
                        self.signal_stats[sig] = {"wins": 0, "losses": 0}
                    if pnl > 0:
                        self.signal_stats[sig]["wins"] += 1
                    else:
                        self.signal_stats[sig]["losses"] += 1
                break

    def get_signal_performance(self) -> list:
        """Return signal win rates for dashboard display."""
        result = []
        for sig, stats in self.signal_stats.items():
            total = stats["wins"] + stats["losses"]
            if total > 0:
                result.append({
                    "signal": sig,
                    "wins": stats["wins"],
                    "losses": stats["losses"],
                    "win_rate": round(stats["wins"] / total * 100, 1),
                    "total": total,
                })
        return sorted(result, key=lambda x: x["win_rate"], reverse=True)

    def get_recent_trades(self, n: int = 20) -> list:
        return self.trade_history[-n:]
