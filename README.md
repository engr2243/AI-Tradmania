# AI-Tradmania

Real-time AI-powered crypto trading bot using Claude API for market analysis and autonomous buy/sell decisions.

## Features

- **Multi-exchange market data** — Binance, Kraken, Bybit in parallel
- **Claude AI decisions** — Real-time buy/sell/hold with reasoning and confidence scores
- **Technical indicators** — RSI, MACD, Bollinger Bands, EMA, Volume analysis
- **Risk management** — Stop-loss, take-profit, position sizing, daily drawdown halt
- **Paper & live trading** — Safe paper mode by default
- **Real-time dashboard** — WebSocket-powered React UI with candlestick charts
- **Trade history** — Full P&L tracking per trade

## Quick Start

### 1. Configure

```bash
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY (required)
```

### 2. Run

```bash
./start.sh
```

Dashboard opens at **http://localhost:5173**

### 3. Docker (alternative)

```bash
cp .env.example .env  # fill in .env first
docker-compose up --build
```

## Architecture

```
Market Feeds (CCXT)  →  Technical Indicators  →  Claude API
       ↓                                              ↓
  Redis Cache          ←──────────────────  Decision Engine
       ↓                                              ↓
  FastAPI + WebSocket                       Portfolio + Risk
       ↓
  React Dashboard (real-time)
```

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | required | Claude API key |
| `TARGET_SYMBOL` | `BTC/USDT` | Trading pair |
| `TRADING_MODE` | `paper` | `paper` or `live` |
| `INITIAL_BALANCE` | `10000` | Starting USDT (paper) |
| `MAX_POSITION_PCT` | `0.10` | Max 10% per trade |
| `STOP_LOSS_PCT` | `0.03` | 3% stop-loss |
| `TAKE_PROFIT_PCT` | `0.05` | 5% take-profit |
| `MAX_DAILY_DRAWDOWN_PCT` | `0.10` | Halt if daily loss > 10% |
| `ANALYSIS_INTERVAL_SECONDS` | `30` | AI cycle interval |
| `EXCHANGES` | `binance,kraken,bybit` | Exchanges to monitor |

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Bot health check |
| GET | `/api/status` | Bot status summary |
| GET | `/api/state` | Full state snapshot |
| GET | `/api/trades` | Trade history |
| GET | `/api/portfolio` | Portfolio state |
| POST | `/api/control` | Start/stop/resume bot |
| POST | `/api/trade` | Manual trade override |
| WS | `/ws` | Real-time state stream |

## Project Structure

```
AI-Tradmania/
├── backend/
│   ├── main.py              # FastAPI + WebSocket server
│   ├── config.py            # Configuration
│   ├── data/
│   │   ├── market_feed.py   # Multi-exchange data
│   │   └── indicators.py    # RSI, MACD, BB, EMA, ATR
│   ├── ai/
│   │   ├── claude_engine.py # Claude API integration
│   │   └── prompt_builder.py
│   ├── trading/
│   │   ├── engine.py        # Main trading loop
│   │   ├── portfolio.py     # Balance + trade tracking
│   │   └── risk.py          # Risk rules enforcement
│   └── api/
│       ├── routes.py        # REST API
│       └── websocket.py     # WS connection manager
├── frontend/
│   └── src/
│       ├── App.jsx           # Main dashboard layout
│       ├── components/
│       │   ├── PriceChart.jsx        # Candlestick + trade markers
│       │   ├── AIDecisions.jsx       # Claude decision log
│       │   ├── Portfolio.jsx         # Balance + P&L
│       │   ├── Indicators.jsx        # Technical indicator panel
│       │   ├── MarketComparison.jsx  # Cross-exchange view
│       │   ├── TradeHistory.jsx      # Trade log table
│       │   └── BotControls.jsx       # Start/stop/config
│       └── hooks/
│           └── useWebSocket.js
├── requirements.txt
├── docker-compose.yml
├── start.sh
└── .env.example
```

## Disclaimer

This software is for educational purposes. Paper trading is enabled by default.
Live trading involves real financial risk. Always test thoroughly before using real funds.
