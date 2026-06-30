"""
Prompt builder — produces structured Chain-of-Thought prompts for Claude.

Techniques implemented:
  1. Multi-timeframe confluence summary
  2. Signal scorecard (pre-scored, not raw numbers)
  3. Chain-of-thought reasoning framework
  4. Fear & Greed context with interpretation
  5. Market regime (ADX-based) with strategy guidance
  6. Decision memory with trade outcomes
  7. Risk/Reward gate calculation
  8. Funding rate context
  9. Support/Resistance levels
"""

from typing import Optional


def build_trading_prompt(
    symbol: str,
    tickers: dict,
    order_books: dict,
    indicators: dict,
    mtf: dict,
    portfolio: dict,
    recent_trades: list,
    decision_memory: list,
    fear_greed: Optional[dict],
    funding_rate: Optional[dict],
    scorecard: dict,
    memory_context: str = "",
    timeframe: str = "5m",
) -> str:

    primary_ticker = next(iter(tickers.values()), {})
    price = primary_ticker.get("last") or 0
    change_pct = primary_ticker.get("change_pct") or 0

    # ── Section 1: Price snapshot ─────────────────────────────────────────────
    exchange_prices = "\n".join(
        f"  {ex}: ${t['last']:,.2f} (24h {t.get('change_pct', 0):+.1f}%)"
        for ex, t in tickers.items() if t.get("last")
    ) or "  N/A"

    primary_ex = next(iter(order_books.keys()), None)
    ob = order_books.get(primary_ex, {})

    # ── Section 2: Signal Scorecard ───────────────────────────────────────────
    scores = scorecard.get("scores", {})
    total = scorecard.get("total", 0)
    max_possible = scorecard.get("max_possible", 17)
    overall_bias = scorecard.get("overall_bias", "neutral")

    def score_bar(s: int, max_s: int = 3) -> str:
        if s > 0:
            return f"+{s}" + " ▲" * s
        elif s < 0:
            return f"{s}" + " ▼" * abs(s)
        return "  0  —"

    scorecard_text = f"""
  Trend (EMA/cross):      {score_bar(scores.get('trend', 0))}
  Momentum (MACD/RSI):    {score_bar(scores.get('momentum', 0))}
  Volume confirmation:    {score_bar(scores.get('volume', 0), 2)}
  MTF Confluence:         {score_bar(scores.get('mtf_confluence', 0))}
  Sentiment (F&G):        {score_bar(scores.get('sentiment', 0), 2)}
  Funding Rate:           {score_bar(scores.get('funding_rate', 0), 2)}
  BB Position:            {score_bar(scores.get('bb_position', 0), 2)}
  ─────────────────────────────────────────
  TOTAL: {total:+d} / {max_possible} possible  →  Overall bias: {overall_bias.upper()}"""

    # ── Section 3: Multi-timeframe analysis ───────────────────────────────────
    alignment = mtf.get("alignment", {}) if mtf else {}
    per_tf = alignment.get("per_tf", {})
    confluence = alignment.get("confluence", "unknown")

    mtf_lines = []
    for tf in ["5m", "1h", "4h"]:
        s = per_tf.get(tf, {})
        if s:
            mtf_lines.append(
                f"  {tf:>3}:  {s.get('bias', '?').upper():<8}  "
                f"EMA {s.get('ema_trend', '?'):<8}  "
                f"MACD {s.get('macd_trend', '?'):<8}  "
                f"RSI {s.get('rsi') or 'N/A':<6}  "
                f"Regime: {s.get('regime', '?')}"
            )
        else:
            mtf_lines.append(f"  {tf:>3}:  insufficient data")

    mtf_text = "\n".join(mtf_lines) + f"\n  → Confluence: {confluence.upper().replace('_', ' ')}"

    # ── Section 4: Key indicators ─────────────────────────────────────────────
    rsi = indicators.get("rsi_14")
    regime = indicators.get("regime", "unknown")
    adx = indicators.get("adx_14")
    vwap = indicators.get("vwap")
    price_vs_vwap = "ABOVE" if price > (vwap or 0) else "BELOW"
    nearest_sup = indicators.get("nearest_support")
    nearest_res = indicators.get("nearest_resistance")
    atr = indicators.get("atr_14") or 0

    sup_gap = f"{((price - nearest_sup) / price * 100):.1f}% below" if nearest_sup else "not detected"
    res_gap = f"{((nearest_res - price) / price * 100):.1f}% above" if nearest_res else "not detected"

    # ── Section 5: Risk/Reward calculation ───────────────────────────────────
    rr_text = _compute_rr_section(price, nearest_sup, nearest_res, atr, portfolio)

    # ── Section 6: Sentiment & Funding ───────────────────────────────────────
    fg_text = "Not available"
    if fear_greed:
        fg_text = (
            f"Score: {fear_greed['score']}/100 — {fear_greed['label']} "
            f"(trending {fear_greed.get('trend', 'unknown')})\n"
            f"  Interpretation: {fear_greed.get('interpretation', '')}"
        )

    funding_text = "Not available"
    if funding_rate:
        rate_pct = funding_rate["rate_pct"]
        if abs(rate_pct) > 0.1:
            signal = "⚠ Extremely bullish crowding → bearish contrarian signal" if rate_pct > 0 else "⚠ Extremely bearish crowding → bullish contrarian signal"
        elif rate_pct > 0.05:
            signal = "Slightly over-leveraged longs → mild bearish signal"
        elif rate_pct < -0.03:
            signal = "Shorts overcrowded → squeeze risk → mild bullish signal"
        else:
            signal = "Neutral — no crowding signal"
        funding_text = f"{rate_pct:+.4f}% per 8h  →  {signal}"

    # ── Section 7: Portfolio state ────────────────────────────────────────────
    balance_usdt = portfolio.get("balance_usdt", 0)
    holdings = portfolio.get("holdings", 0)
    holdings_value = holdings * price if price else 0
    total_value = portfolio.get("total_value", balance_usdt)
    unrealized_pnl = portfolio.get("unrealized_pnl", 0)
    realized_pnl = portfolio.get("realized_pnl", 0)
    avg_buy = portfolio.get("avg_buy_price")
    daily_drawdown = portfolio.get("daily_drawdown_pct", 0)

    base = symbol.split("/")[0]

    # ── Section 8: Decision memory ────────────────────────────────────────────
    memory_text = _format_decision_memory(decision_memory)

    # ── Section 9: Long-term graph memory ────────────────────────────────────
    memory_section = ""
    if memory_context and memory_context.strip():
        memory_section = f"""
────────────────────────────────────────────────────────
LONG-TERM MEMORY INSIGHTS  (Neo4j learned patterns)
────────────────────────────────────────────────────────
{memory_context}"""

    # ── Section 10: Regime-based strategy hint ────────────────────────────────
    strategy_hint = _regime_strategy_hint(regime, adx, confluence)

    # ── Section 10: Market regime warning ─────────────────────────────────────
    if avg_buy and holdings > 0:
        entry_change = (price - avg_buy) / avg_buy * 100
        position_status = f"  In position: avg buy ${avg_buy:,.2f} | Current change: {entry_change:+.2f}%"
    else:
        position_status = "  No open position"

    prompt = f"""You are an expert quantitative crypto trading analyst. Analyze the following structured market data and make a precise trading decision using the Chain-of-Thought framework below.

════════════════════════════════════════════════════════
MARKET: {symbol}  |  Price: ${price:,.2f}  |  24h Change: {change_pct:+.1f}%
════════════════════════════════════════════════════════

EXCHANGE PRICES (cross-market):
{exchange_prices}

ORDER BOOK ({primary_ex or 'N/A'}):
  Buy Pressure: {ob.get('buy_pressure_pct', 50):.0f}%  |  Spread: ${ob.get('spread', 0):.2f}
  Bid Vol: {ob.get('bid_volume', 0):.2f}  |  Ask Vol: {ob.get('ask_volume', 0):.2f}

────────────────────────────────────────────────────────
SIGNAL SCORECARD  (pre-scored for you)
────────────────────────────────────────────────────────
{scorecard_text}

────────────────────────────────────────────────────────
MULTI-TIMEFRAME CONFLUENCE
────────────────────────────────────────────────────────
{mtf_text}

────────────────────────────────────────────────────────
KEY INDICATORS  (5m timeframe)
────────────────────────────────────────────────────────
  RSI(14): {rsi or 'N/A'}  |  MACD: {indicators.get('macd_trend')} (crossing: {indicators.get('macd_crossing')})
  ADX(14): {adx or 'N/A'}  →  Market Regime: {regime.upper().replace('_', ' ')}
  EMA Trend: {indicators.get('ema_trend')}  |  Golden Cross: {indicators.get('golden_cross')}
  BB %B: {indicators.get('bb_pct')}  |  Squeeze: {indicators.get('bb_squeeze')}
  VWAP: ${vwap or 'N/A'}  →  Price is {price_vs_vwap} VWAP (bullish if above)
  Volume ratio: {indicators.get('volume_ratio')}x 20-period avg
  Momentum 5-bar: {indicators.get('momentum_5')}%
  ATR(14): {atr}

KEY PRICE LEVELS:
  Nearest Support:    ${nearest_sup or 'N/A'}  ({sup_gap})
  Nearest Resistance: ${nearest_res or 'N/A'}  ({res_gap})

────────────────────────────────────────────────────────
RISK / REWARD ANALYSIS
────────────────────────────────────────────────────────
{rr_text}

────────────────────────────────────────────────────────
EXTERNAL SIGNALS
────────────────────────────────────────────────────────
Fear & Greed Index:
  {fg_text}

Binance Perpetual Funding Rate:
  {funding_text}

────────────────────────────────────────────────────────
PORTFOLIO STATE
────────────────────────────────────────────────────────
  USDT Balance: ${balance_usdt:,.2f}
  {base} Holdings: {holdings:.6f}  (≈${holdings_value:,.2f})
  Total Value: ${total_value:,.2f}
  Unrealized P&L: ${unrealized_pnl:+,.2f}  |  Realized P&L: ${realized_pnl:+,.2f}
  Daily Drawdown: {daily_drawdown:.1f}%
{position_status}

────────────────────────────────────────────────────────
YOUR DECISION HISTORY (last {len(decision_memory)} decisions)
────────────────────────────────────────────────────────
{memory_text}
{memory_section}
════════════════════════════════════════════════════════
STRATEGY GUIDANCE FOR CURRENT REGIME
════════════════════════════════════════════════════════
{strategy_hint}

════════════════════════════════════════════════════════
CHAIN-OF-THOUGHT ANALYSIS — work through each step:
════════════════════════════════════════════════════════

STEP 1 — REGIME: Is the market trending or ranging? What does ADX + MTF tell you?
STEP 2 — TREND DIRECTION: What is the dominant direction across timeframes?
STEP 3 — SIGNAL QUALITY: Are multiple signals aligned (scorecard total, confluence)?
STEP 4 — ENTRY TIMING: Is now a good entry point or are we chasing? Check RSI, BB, VWAP.
STEP 5 — RISK/REWARD: Does the R:R ratio meet the 1.5x minimum threshold?
STEP 6 — SENTIMENT OVERLAY: What does Fear & Greed + Funding Rate add to the picture?
STEP 7 — FINAL DECISION: Synthesize all above into one clear action.

⚠ RULE: Only BUY/SELL if R:R ≥ 1.5. If R:R < 1.5, output HOLD regardless of signal strength.
⚠ RULE: MTF confluence = "mixed" → reduce confidence by 20% and amount_pct by 30%.
⚠ RULE: If you are in a position, always state whether stop-loss or take-profit is near.

Respond ONLY with valid JSON:
{{
  "reasoning": {{
    "step1_regime": "<regime assessment>",
    "step2_trend": "<trend direction reasoning>",
    "step3_signals": "<signal quality assessment>",
    "step4_timing": "<entry timing assessment>",
    "step5_rr": "<R:R calculation and pass/fail>",
    "step6_sentiment": "<sentiment + funding assessment>",
    "step7_decision": "<final synthesis>"
  }},
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": <0.0 to 1.0>,
  "amount_pct": <0 to 100>,
  "reason": "<2-3 sentence human-readable summary of the decision>",
  "key_signals": ["signal1", "signal2", "signal3"],
  "risk_level": "LOW" | "MEDIUM" | "HIGH",
  "target_price": <price target or null>,
  "stop_loss": <stop loss price or null>,
  "rr_ratio": <calculated R:R ratio or null>
}}"""

    return prompt


def _compute_rr_section(
    price: float,
    nearest_sup: Optional[float],
    nearest_res: Optional[float],
    atr: float,
    portfolio: dict,
) -> str:
    avg_buy = portfolio.get("avg_buy_price")
    holdings = portfolio.get("holdings", 0)

    # ATR-based levels
    atr_stop = round(price - 1.5 * atr, 2) if atr else None
    atr_target = round(price + 2.5 * atr, 2) if atr else None

    # S/R-based levels
    sr_stop = nearest_sup if nearest_sup and nearest_sup < price * 0.98 else atr_stop
    sr_target = nearest_res if nearest_res and nearest_res > price * 1.01 else atr_target

    lines = []
    if sr_stop and sr_target:
        risk = price - sr_stop
        reward = sr_target - price
        rr = reward / risk if risk > 0 else 0
        gate = "✓ PASSES" if rr >= 1.5 else "✗ FAILS (do not trade)"
        lines.append(f"  Potential entry:  ${price:,.2f}")
        lines.append(f"  Stop-loss level:  ${sr_stop:,.2f}  (risk: ${risk:,.2f})")
        lines.append(f"  Target level:     ${sr_target:,.2f}  (reward: ${reward:,.2f})")
        lines.append(f"  R:R Ratio:        {rr:.2f}x  →  {gate}")
    else:
        lines.append("  R:R cannot be calculated (insufficient S/R data)")

    if avg_buy and holdings > 0:
        pnl_pct = (price - avg_buy) / avg_buy * 100
        lines.append(f"\n  Existing position P&L: {pnl_pct:+.2f}% from avg entry ${avg_buy:,.2f}")

    return "\n".join(lines)


def _format_decision_memory(memory: list) -> str:
    if not memory:
        return "  No prior decisions this session."
    lines = []
    for d in memory[-8:]:
        action = d.get("action", "?")
        confidence = d.get("confidence", 0)
        outcome = d.get("outcome", "pending")
        pnl = d.get("pnl")
        price_at = d.get("price_at")
        key_signals = ", ".join(d.get("key_signals", [])[:2])
        pnl_str = f"→ P&L: ${pnl:+.2f}" if pnl is not None else ""
        outcome_icon = {"profit": "✓", "loss": "✗", "pending": "⏳", "avoided_loss": "~"}.get(outcome, "?")
        lines.append(
            f"  {outcome_icon} {action:<4} conf:{confidence:.0%}  price:${price_at or 0:,.0f}  "
            f"signals:[{key_signals}]  {pnl_str}  ({outcome})"
        )
    return "\n".join(lines)


def _regime_strategy_hint(regime: str, adx: Optional[float], confluence: str) -> str:
    hints = []
    if regime == "strong_trend":
        hints.append("STRONG TREND MARKET (ADX > 40): Use momentum-following signals. RSI oversold/overbought are LESS reliable — ignore them. Follow EMA direction. MACD crossovers are your primary signal.")
    elif regime == "trending":
        hints.append("TRENDING MARKET (ADX 25-40): Trend-following is optimal. Enter on pullbacks to EMA21. Avoid counter-trend trades. Raise stop-loss aggressively as profit grows.")
    else:
        hints.append("RANGING MARKET (ADX < 25): Mean-reversion is optimal. RSI oversold/overbought are MORE reliable. Trade BB bounces. Avoid breakout signals — likely false. Use tighter targets.")

    if confluence == "strong_bullish":
        hints.append("ALL TIMEFRAMES ALIGNED BULLISH — highest confidence setup. Full position size appropriate.")
    elif confluence == "strong_bearish":
        hints.append("ALL TIMEFRAMES ALIGNED BEARISH — highest confidence short setup.")
    elif confluence == "mixed":
        hints.append("MIXED TIMEFRAME SIGNALS — reduce position size by 30%, lower confidence threshold.")
    elif "mild" in confluence:
        hints.append(f"PARTIAL CONFLUENCE ({confluence.replace('_', ' ')}) — moderate confidence. Standard position sizing.")

    return "\n".join(hints)
