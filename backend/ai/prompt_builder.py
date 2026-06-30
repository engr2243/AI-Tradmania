import json
from data.indicators import format_indicators_summary


def build_trading_prompt(
    symbol: str,
    tickers: dict,
    order_books: dict,
    indicators: dict,
    portfolio: dict,
    recent_trades: list,
    timeframe: str = "5m",
) -> str:
    primary_ticker = next(iter(tickers.values()), {}) if tickers else {}
    price = primary_ticker.get("last", "N/A")
    change_pct = primary_ticker.get("change_pct", "N/A")

    # Multi-exchange price comparison
    exchange_prices = []
    for ex, t in tickers.items():
        if t.get("last"):
            exchange_prices.append(f"  {ex}: ${t['last']:,.2f}")
    exchange_summary = "\n".join(exchange_prices) if exchange_prices else "  N/A"

    # Order book from primary exchange
    primary_ex = next(iter(order_books.keys()), None)
    ob = order_books.get(primary_ex, {})
    buy_pressure = ob.get("buy_pressure_pct", 50)
    spread = ob.get("spread", "N/A")

    # Portfolio state
    balance_usdt = portfolio.get("balance_usdt", 0)
    holdings = portfolio.get("holdings", 0)
    holdings_value = holdings * float(price) if isinstance(price, (int, float)) else 0
    total_value = balance_usdt + holdings_value
    unrealized_pnl = portfolio.get("unrealized_pnl", 0)
    realized_pnl = portfolio.get("realized_pnl", 0)
    daily_drawdown = portfolio.get("daily_drawdown_pct", 0)

    # Recent trades summary
    trades_text = "None yet"
    if recent_trades:
        trade_lines = []
        for t in recent_trades[-3:]:
            trade_lines.append(
                f"  {t['side'].upper()} {t['amount']:.4f} @ ${t['price']:,.2f} "
                f"| P&L: {t.get('pnl', 0):+.2f} USDT"
            )
        trades_text = "\n".join(trade_lines)

    indicators_text = format_indicators_summary(indicators)

    prompt = f"""You are an expert crypto trading AI assistant. Analyze the following real-time market data and make a precise trading decision.

=== MARKET DATA: {symbol} | Timeframe: {timeframe} ===

Current Prices (multi-exchange):
{exchange_summary}

Primary Price: ${price:,.2f} | 24h Change: {change_pct}%
24h High: ${primary_ticker.get('high', 'N/A'):,} | 24h Low: ${primary_ticker.get('low', 'N/A'):,}

Order Book ({primary_ex}):
  Buy Pressure: {buy_pressure}% | Spread: ${spread}
  Bid Volume: {ob.get('bid_volume', 'N/A')} | Ask Volume: {ob.get('ask_volume', 'N/A')}

=== TECHNICAL INDICATORS ===
{indicators_text}

=== PORTFOLIO STATE ===
USDT Balance: ${balance_usdt:,.2f}
{symbol.split('/')[0]} Holdings: {holdings:.6f} (≈${holdings_value:,.2f})
Total Portfolio Value: ${total_value:,.2f}
Unrealized P&L: ${unrealized_pnl:+,.2f}
Realized P&L (session): ${realized_pnl:+,.2f}
Daily Drawdown: {daily_drawdown:.1f}%

=== RECENT TRADES ===
{trades_text}

=== DECISION REQUIRED ===
Based on the above data, provide your trading decision.

Rules:
- BUY: Enter or add to position when you see a strong bullish signal
- SELL: Exit or reduce position when you see a strong bearish signal or profit target met
- HOLD: No action when signals are mixed or risk is too high

Respond ONLY with valid JSON in this exact format:
{{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": <0.0 to 1.0>,
  "amount_pct": <0 to 100, percentage of available capital to use>,
  "reason": "<2-3 sentence explanation of the key signals driving this decision>",
  "key_signals": ["signal1", "signal2", "signal3"],
  "risk_level": "LOW" | "MEDIUM" | "HIGH",
  "target_price": <optional price target>,
  "stop_loss": <optional stop loss price>
}}"""

    return prompt
