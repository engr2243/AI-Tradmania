import logging
from config import (
    MAX_POSITION_PCT,
    STOP_LOSS_PCT,
    TAKE_PROFIT_PCT,
    MAX_DAILY_DRAWDOWN_PCT,
)

logger = logging.getLogger(__name__)


class RiskManager:
    def __init__(self):
        self.halt = False
        self.halt_reason = ""

    def validate_buy(self, decision: dict, portfolio_state: dict, current_price: float) -> tuple[bool, float, str]:
        if self.halt:
            return False, 0, f"Bot halted: {self.halt_reason}"

        # Daily drawdown guard
        if portfolio_state["daily_drawdown_pct"] >= MAX_DAILY_DRAWDOWN_PCT * 100:
            self.halt = True
            self.halt_reason = f"Daily drawdown limit reached ({portfolio_state['daily_drawdown_pct']:.1f}%)"
            return False, 0, self.halt_reason

        # Confidence gate
        if decision["confidence"] < 0.6:
            return False, 0, f"Confidence too low ({decision['confidence']:.2f} < 0.60)"

        # Position sizing: cap at MAX_POSITION_PCT of total portfolio
        balance = portfolio_state["balance_usdt"]
        total = portfolio_state["total_value"]
        max_spend = total * MAX_POSITION_PCT
        requested_pct = decision.get("amount_pct", 50) / 100
        spend = min(balance * requested_pct, max_spend, balance)

        if spend < 1:
            return False, 0, "Insufficient balance for BUY"

        return True, round(spend, 4), "Risk checks passed"

    def validate_sell(self, decision: dict, portfolio_state: dict, current_price: float) -> tuple[bool, float, str]:
        if self.halt:
            return False, 0, f"Bot halted: {self.halt_reason}"

        holdings = portfolio_state["holdings"]
        if holdings <= 0:
            return False, 0, "No holdings to sell"

        if decision["confidence"] < 0.55:
            return False, 0, f"Confidence too low for SELL ({decision['confidence']:.2f})"

        amount_pct = decision.get("amount_pct", 100)
        return True, amount_pct, "Risk checks passed"

    def check_stop_loss_take_profit(self, portfolio_state: dict, current_price: float) -> dict:
        result = {"trigger": None, "reason": ""}

        avg_buy = portfolio_state.get("avg_buy_price")
        holdings = portfolio_state.get("holdings", 0)

        if not avg_buy or holdings <= 0:
            return result

        change_pct = (current_price - avg_buy) / avg_buy

        if change_pct <= -STOP_LOSS_PCT:
            result["trigger"] = "SELL"
            result["reason"] = f"Stop-loss triggered: {change_pct*100:.2f}% (limit: -{STOP_LOSS_PCT*100:.1f}%)"
            result["amount_pct"] = 100
            logger.warning(result["reason"])

        elif change_pct >= TAKE_PROFIT_PCT:
            result["trigger"] = "SELL"
            result["reason"] = f"Take-profit triggered: +{change_pct*100:.2f}% (target: +{TAKE_PROFIT_PCT*100:.1f}%)"
            result["amount_pct"] = 100
            logger.info(result["reason"])

        return result

    def resume(self):
        self.halt = False
        self.halt_reason = ""
