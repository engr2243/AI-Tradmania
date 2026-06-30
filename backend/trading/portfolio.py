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

    def get_state(self, current_price: Optional[float] = None) -> dict:
        holdings_value = (self.holdings * current_price) if current_price and self.holdings else 0
        total_value = self.balance_usdt + holdings_value

        unrealized_pnl = 0.0
        if self.holdings > 0 and self.avg_buy_price and current_price:
            unrealized_pnl = (current_price - self.avg_buy_price) * self.holdings

        # Reset daily stats if new day
        if time.time() - self.day_start_time > 86400:
            self.day_start_value = total_value
            self.day_start_time = time.time()

        daily_drawdown_pct = 0.0
        if self.day_start_value > 0:
            daily_drawdown_pct = max(0, (self.day_start_value - total_value) / self.day_start_value * 100)

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
        }

    def apply_buy(self, price: float, amount_usdt: float, fee_pct: float = 0.001) -> Optional[dict]:
        if amount_usdt > self.balance_usdt:
            amount_usdt = self.balance_usdt
        if amount_usdt <= 0:
            return None

        fee = amount_usdt * fee_pct
        net_usdt = amount_usdt - fee
        qty = net_usdt / price

        # Update average buy price
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

    def sync_from_exchange(self, balances: dict, current_price: float):
        """Overwrite portfolio state with real Binance balances after a live trade."""
        self.balance_usdt = balances["usdt_free"]
        self.holdings = balances["base_free"]
        if self.holdings > 0 and self.avg_buy_price is None:
            # Estimate avg buy price from current price if unknown
            self.avg_buy_price = current_price
        logger.info(
            f"Portfolio synced from Binance | USDT: ${self.balance_usdt:.2f} | Holdings: {self.holdings:.8f}"
        )

    def record_live_trade(self, order: dict, pnl: float = 0) -> dict:
        """Record a live order returned by BinanceLiveExecutor into trade history."""
        trade = {**order, "id": len(self.trade_history) + 1, "pnl": round(pnl, 4)}
        self.trade_history.append(trade)
        self.realized_pnl += pnl
        return trade

    def get_recent_trades(self, n: int = 10) -> list:
        return self.trade_history[-n:]
