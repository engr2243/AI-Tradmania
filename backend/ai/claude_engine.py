import json
import logging
import re
import time
from typing import Optional
import anthropic

from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def parse_decision(raw: str) -> Optional[dict]:
    try:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            return None
        data = json.loads(match.group())
        action = data.get("action", "").upper()
        if action not in ("BUY", "SELL", "HOLD"):
            return None
        return {
            "action": action,
            "confidence": float(data.get("confidence", 0.5)),
            "amount_pct": float(data.get("amount_pct", 0)),
            "reason": data.get("reason", ""),
            "key_signals": data.get("key_signals", []),
            "risk_level": data.get("risk_level", "MEDIUM"),
            "target_price": data.get("target_price"),
            "stop_loss": data.get("stop_loss"),
            "rr_ratio": data.get("rr_ratio"),
            "reasoning": data.get("reasoning", {}),
        }
    except Exception as e:
        logger.warning(f"Decision parse error: {e} | raw: {raw[:200]}")
        return None


def analyze_market(prompt: str) -> dict:
    start = time.time()
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
        decision = parse_decision(raw)
        elapsed = round(time.time() - start, 2)

        if decision is None:
            logger.warning(f"Could not parse Claude response: {raw[:300]}")
            return _hold_response("Failed to parse AI response. Defaulting to HOLD.", elapsed)

        decision["raw"] = raw
        decision["latency_s"] = elapsed
        decision["error"] = False
        logger.info(
            f"Claude decision: {decision['action']} | "
            f"conf: {decision['confidence']:.0%} | "
            f"R:R: {decision.get('rr_ratio')} | "
            f"latency: {elapsed}s"
        )
        return decision

    except anthropic.AuthenticationError:
        return _hold_response(
            "Invalid or missing ANTHROPIC_API_KEY. Add it to .env to enable AI decisions.",
            round(time.time() - start, 2),
            key_signals=["api_key_missing"],
        )
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return _hold_response(f"AI engine error: {str(e)[:100]}", round(time.time() - start, 2))


def _hold_response(reason: str, latency: float, key_signals: list = None) -> dict:
    return {
        "action": "HOLD",
        "confidence": 0.0,
        "amount_pct": 0,
        "reason": reason,
        "key_signals": key_signals or [],
        "risk_level": "HIGH",
        "target_price": None,
        "stop_loss": None,
        "rr_ratio": None,
        "reasoning": {},
        "latency_s": latency,
        "error": True,
    }
