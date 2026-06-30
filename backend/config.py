import os
from dotenv import load_dotenv

load_dotenv()

# Claude API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Exchange API keys (optional for paper trading)
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET = os.getenv("BINANCE_SECRET", "")
KRAKEN_API_KEY = os.getenv("KRAKEN_API_KEY", "")
KRAKEN_SECRET = os.getenv("KRAKEN_SECRET", "")
COINBASE_API_KEY = os.getenv("COINBASE_API_KEY", "")
COINBASE_SECRET = os.getenv("COINBASE_SECRET", "")

# Trading config
TARGET_SYMBOL = os.getenv("TARGET_SYMBOL", "BTC/USDT")
TRADING_MODE = os.getenv("TRADING_MODE", "paper")  # paper | live
INITIAL_BALANCE = float(os.getenv("INITIAL_BALANCE", "10000"))
MAX_POSITION_PCT = float(os.getenv("MAX_POSITION_PCT", "0.10"))
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "0.03"))
TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", "0.05"))
MAX_DAILY_DRAWDOWN_PCT = float(os.getenv("MAX_DAILY_DRAWDOWN_PCT", "0.10"))
ANALYSIS_INTERVAL_SECONDS = int(os.getenv("ANALYSIS_INTERVAL_SECONDS", "30"))

# Exchanges to monitor
EXCHANGES = os.getenv("EXCHANGES", "binance,kraken,bybit").split(",")

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Neo4j (long-term memory graph)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "tradmania")
