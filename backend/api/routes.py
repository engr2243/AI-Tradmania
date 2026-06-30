from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api")

# Injected by main.py
engine = None


def set_engine(e):
    global engine
    engine = e


class BotControl(BaseModel):
    action: str  # start | stop | resume
    symbol: Optional[str] = None
    mode: Optional[str] = None


class TradeOverride(BaseModel):
    action: str  # BUY | SELL | HOLD
    amount_pct: float = 50.0


@router.get("/status")
async def get_status():
    if not engine:
        return {"status": "not_initialized"}
    state = engine.get_full_state()
    return {
        "status": "running" if engine.running else "stopped",
        "mode": engine.mode,
        "symbol": engine.symbol,
        "cycle": engine.cycle_count,
        "portfolio": state["portfolio"],
        "risk_halted": state["risk_halted"],
        "halt_reason": state["halt_reason"],
    }


@router.get("/state")
async def get_full_state():
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return engine.get_full_state()


@router.get("/trades")
async def get_trades(limit: int = 50):
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    trades = engine.portfolio.get_recent_trades(limit)
    return {"trades": trades, "total": len(engine.portfolio.trade_history)}


@router.get("/portfolio")
async def get_portfolio():
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    tickers = engine.last_market_data.get("tickers", {})
    primary = next(iter(tickers.values()), {})
    price = primary.get("last")
    return engine.portfolio.get_state(price)


@router.post("/control")
async def control_bot(body: BotControl):
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    if body.action == "stop":
        await engine.stop()
        return {"message": "Bot stopped"}

    elif body.action == "start":
        if engine.running:
            return {"message": "Bot already running"}
        if body.symbol:
            engine.set_symbol(body.symbol)
        if body.mode:
            engine.set_mode(body.mode)
        await engine.start()
        return {"message": "Bot started", "symbol": engine.symbol, "mode": engine.mode}

    elif body.action == "resume":
        engine.risk.resume()
        return {"message": "Risk halt cleared, bot resumed"}

    raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")


@router.post("/trade")
async def manual_trade(body: TradeOverride):
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    tickers = engine.last_market_data.get("tickers", {})
    primary = next(iter(tickers.values()), {})
    price = primary.get("last")

    if not price:
        raise HTTPException(status_code=400, detail="No price data available")

    decision = {
        "action": body.action.upper(),
        "confidence": 1.0,
        "amount_pct": body.amount_pct,
        "reason": "Manual override by user",
        "key_signals": ["manual_trade"],
        "risk_level": "MEDIUM",
    }

    trade = None
    if decision["action"] == "BUY":
        trade = engine._execute_buy(decision, price)
    elif decision["action"] == "SELL":
        trade = engine._execute_sell(decision, price)

    if trade is None:
        raise HTTPException(status_code=400, detail="Trade not executed (risk check failed or no holdings)")

    return {"trade": trade, "portfolio": engine.portfolio.get_state(price)}


@router.get("/decisions")
async def get_decisions():
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return {"last_decision": engine.last_decision}
