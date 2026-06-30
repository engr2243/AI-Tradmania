import logging
import time
from datetime import datetime, timezone
from typing import Optional

from config import (
    MAX_POSITION_PCT,
    STOP_LOSS_PCT,
    TAKE_PROFIT_PCT,
    MAX_DAILY_DRAWDOWN_PCT,
)

logger = logging.getLogger(__name__)

MIN_RR_RATIO = 1.5         # Minimum risk/reward to allow a trade
MIN_CONFIDENCE_BUY = 0.60
MIN_CONFIDENCE_SELL = 0.55

# Low-liquidity UTC hours to avoid (00:00–06:00 UTC)
LOW_LIQUIDITY_HOURS_UTC = set(range(0, 6))


class RiskManager:
    def __init__(self):
        self.halt = False
        self.halt_reason = ""
        self.consecutive_losses = 0
        self.last_loss_time: Optional[float] = None

    # ── Public validators ────────────────────────────────────────────────────

    def validate_buy(self, decision: dict, portfolio_state: dict, current_price: float) -> tuple[bool, float, str]:
        if self.halt:
            return False, 0, f"Bot halted: {self.halt_reason}"

        checks = [
            self._check_daily_drawdown(portfolio_state),
            self._check_time_filter(),
            self._check_confidence(decision, MIN_CONFIDENCE_BUY),
            self._check_rr_ratio(decision),
            self._check_consecutive_losses(),
        ]
        for ok, msg in checks:
            if not ok:
                return False, 0, msg

        balance = portfolio_state["balance_usdt"]
        total = portfolio_state["total_value"]
        scale = self._loss_scale_factor()
        max_spend = total * MAX_POSITION_PCT * scale
        requested_pct = decision.get("amount_pct", 50) / 100
        spend = min(balance * requested_pct * scale, max_spend, balance)

        if spend < 1:
            return False, 0, "Insufficient balance for BUY"

        msg = "Risk checks passed"
        if scale < 1.0:
            msg += f" (position scaled to {scale*100:.0f}% due to {self.consecutive_losses} consecutive losses)"

        return True, round(spend, 4), msg

    def validate_sell(self, decision: dict, portfolio_state: dict, current_price: float) -> tuple[bool, float, str]:
        if self.halt:
            return False, 0, f"Bot halted: {self.halt_reason}"

        if portfolio_state.get("holdings", 0) <= 0:
            return False, 0, "No holdings to sell"

        ok, msg = self._check_confidence(decision, MIN_CONFIDENCE_SELL)
        if not ok:
            return False, 0, msg

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
            result.update({
                "trigger": "SELL",
                "reason": f"Stop-loss triggered: {change_pct*100:.2f}% (limit: -{STOP_LOSS_PCT*100:.1f}%)",
                "amount_pct": 100,
            })
            logger.warning(result["reason"])
        elif change_pct >= TAKE_PROFIT_PCT:
            result.update({
                "trigger": "SELL",
                "reason": f"Take-profit triggered: +{change_pct*100:.2f}% (target: +{TAKE_PROFIT_PCT*100:.1f}%)",
                "amount_pct": 100,
            })
            logger.info(result["reason"])

        return result

    def record_trade_outcome(self, pnl: float):
        """Call after each completed trade to update streak tracking."""
        if pnl < 0:
            self.consecutive_losses += 1
            self.last_loss_time = time.time()
            logger.warning(f"Loss recorded. Consecutive losses: {self.consecutive_losses}")
            if self.consecutive_losses >= 4:
                self.halt = True
                self.halt_reason = (
                    f"4 consecutive losses — bot paused for review. "
                    f"Total streak loss. Call /api/control resume to restart."
                )
        else:
            self.consecutive_losses = 0
            logger.info("Win recorded. Loss streak reset.")

    def resume(self):
        self.halt = False
        self.halt_reason = ""
        self.consecutive_losses = 0

    def get_status(self) -> dict:
        return {
            "halt": self.halt,
            "halt_reason": self.halt_reason,
            "consecutive_losses": self.consecutive_losses,
            "position_scale": self._loss_scale_factor(),
        }

    # ── Private checks ───────────────────────────────────────────────────────

    def _check_daily_drawdown(self, portfolio_state: dict) -> tuple[bool, str]:
        dd = portfolio_state.get("daily_drawdown_pct", 0)
        if dd >= MAX_DAILY_DRAWDOWN_PCT * 100:
            self.halt = True
            self.halt_reason = f"Daily drawdown limit reached ({dd:.1f}%)"
            return False, self.halt_reason
        return True, ""

    def _check_time_filter(self) -> tuple[bool, str]:
        """Block trades during low-liquidity UTC hours (00:00–06:00 UTC)."""
        current_hour = datetime.now(timezone.utc).hour
        if current_hour in LOW_LIQUIDITY_HOURS_UTC:
            return False, (
                f"Low-liquidity window (UTC {current_hour:02d}:00). "
                "Skipping to avoid fakeouts. Resumes at 06:00 UTC."
            )
        return True, ""

    def _check_confidence(self, decision: dict, min_conf: float) -> tuple[bool, str]:
        conf = decision.get("confidence", 0)
        if conf < min_conf:
            return False, f"Confidence {conf:.2f} below minimum {min_conf:.2f}"
        return True, ""

    def _check_rr_ratio(self, decision: dict) -> tuple[bool, str]:
        """Enforce minimum R:R of 1.5 — only Claude can provide this."""
        rr = decision.get("rr_ratio")
        if rr is None:
            # If Claude didn't compute it, we allow it through (no data = no block)
            return True, ""
        if rr < MIN_RR_RATIO:
            return False, f"R:R ratio {rr:.2f}x below minimum {MIN_RR_RATIO}x — skipping trade"
        return True, ""

    def _check_consecutive_losses(self) -> tuple[bool, str]:
        if self.consecutive_losses >= 4:
            if not self.halt:
                self.halt = True
                self.halt_reason = f"4 consecutive losses — paused for review"
            return False, self.halt_reason
        return True, ""

    def _loss_scale_factor(self) -> float:
        """Scale down position size after consecutive losses."""
        if self.consecutive_losses == 0:
            return 1.0
        elif self.consecutive_losses == 1:
            return 1.0   # first loss: no penalty
        elif self.consecutive_losses == 2:
            return 0.70  # two losses: 70% size
        elif self.consecutive_losses == 3:
            return 0.50  # three losses: 50% size
        return 0.0       # four+ losses: halt
