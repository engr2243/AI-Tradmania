"""
Multi-provider AI engine abstraction.

Supported providers:
  - claude    : Anthropic Claude (via anthropic SDK)
  - openai    : OpenAI GPT (via openai SDK)
  - moonshot  : Moonshot AI / Kimi (OpenAI-compatible API)
  - deepseek  : DeepSeek (OpenAI-compatible API)
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)

FALLBACK_DECISION = {
    "action": "HOLD",
    "confidence": 0.5,
    "amount_pct": 0,
    "reason": "AI provider error — holding to preserve capital.",
    "key_signals": ["provider_error"],
    "risk_level": "HIGH",
    "target_price": None,
    "stop_loss": None,
    "rr_ratio": None,
    "reasoning": {},
    "error": True,
}


def _extract_json(text: str) -> dict:
    """Extract and parse JSON from a provider response string."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strip markdown code fences if present
    if "```" in text:
        start = text.find("```")
        end = text.rfind("```")
        if end > start:
            inner = text[start + 3:end]
            if inner.startswith("json"):
                inner = inner[4:]
            try:
                return json.loads(inner.strip())
            except json.JSONDecodeError:
                pass
    # Last resort: find outermost braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    logger.error(f"Failed to parse JSON from AI response: {text[:300]}")
    return {}


def _normalise(decision: dict, provider_name: str, latency_s: float) -> dict:
    """Ensure all expected fields are present regardless of provider."""
    decision.setdefault("action", "HOLD")
    decision.setdefault("confidence", 0.5)
    decision.setdefault("amount_pct", 0)
    decision.setdefault("reason", "No reason provided.")
    decision.setdefault("key_signals", [])
    decision.setdefault("risk_level", "MEDIUM")
    decision.setdefault("target_price", None)
    decision.setdefault("stop_loss", None)
    decision.setdefault("rr_ratio", None)
    decision.setdefault("reasoning", {})
    decision["provider"] = provider_name
    decision["latency_s"] = round(latency_s, 2)
    decision.pop("error", None)
    return decision


class AIProvider(ABC):
    name: str = "unknown"
    model: str = "unknown"

    @abstractmethod
    def analyze(self, prompt: str) -> dict:
        pass


# ── Claude (Anthropic) ────────────────────────────────────────────────────────

class ClaudeProvider(AIProvider):
    name = "claude"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def analyze(self, prompt: str) -> dict:
        t0 = time.time()
        try:
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text.strip()
            decision = _extract_json(text)
            if not decision:
                return {**FALLBACK_DECISION, "reason": "Claude returned unparseable response."}
            return _normalise(decision, self.name, time.time() - t0)
        except Exception as e:
            logger.error(f"Claude error: {e}")
            return {**FALLBACK_DECISION, "reason": f"Claude API error: {e}"}


# ── OpenAI-compatible base (OpenAI / Moonshot / DeepSeek) ────────────────────

class OpenAICompatibleProvider(AIProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        provider_name: str,
        base_url: Optional[str] = None,
    ):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.name = provider_name

    def analyze(self, prompt: str) -> dict:
        t0 = time.time()
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a quantitative crypto trading analyst. "
                            "Always respond with valid JSON only — no markdown, no explanation."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            text = resp.choices[0].message.content.strip()
            decision = _extract_json(text)
            if not decision:
                return {**FALLBACK_DECISION, "reason": f"{self.name} returned unparseable response."}
            return _normalise(decision, self.name, time.time() - t0)
        except Exception as e:
            logger.error(f"{self.name} error: {e}")
            return {**FALLBACK_DECISION, "reason": f"{self.name} API error: {e}"}


# ── Factory ───────────────────────────────────────────────────────────────────

def get_provider(override: Optional[str] = None) -> AIProvider:
    from config import (
        AI_PROVIDER,
        ANTHROPIC_API_KEY, CLAUDE_MODEL,
        OPENAI_API_KEY, OPENAI_MODEL,
        MOONSHOT_API_KEY, MOONSHOT_MODEL,
        DEEPSEEK_API_KEY, DEEPSEEK_MODEL,
    )

    name = (override or AI_PROVIDER).lower()

    if name == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set")
        return OpenAICompatibleProvider(
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            provider_name="openai",
        )

    if name == "moonshot":
        if not MOONSHOT_API_KEY:
            raise ValueError("MOONSHOT_API_KEY not set")
        return OpenAICompatibleProvider(
            api_key=MOONSHOT_API_KEY,
            model=MOONSHOT_MODEL,
            provider_name="moonshot",
            base_url="https://api.moonshot.cn/v1",
        )

    if name == "deepseek":
        if not DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY not set")
        return OpenAICompatibleProvider(
            api_key=DEEPSEEK_API_KEY,
            model=DEEPSEEK_MODEL,
            provider_name="deepseek",
            base_url="https://api.deepseek.com/v1",
        )

    # Default: Claude
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set")
    return ClaudeProvider(api_key=ANTHROPIC_API_KEY, model=CLAUDE_MODEL)
