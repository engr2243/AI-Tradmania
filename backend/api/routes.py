from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api")

engine = None


def set_engine(e):
    global engine
    engine = e


class BotControl(BaseModel):
    action: str
    symbol: Optional[str] = None
    mode: Optional[str] = None


class TradeOverride(BaseModel):
    action: str
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
        "risk": state["risk"],
        "risk_halted": state["risk_halted"],
        "halt_reason": state["halt_reason"],
        "scorecard": state.get("scorecard"),
        "fear_greed": state.get("fear_greed"),
        "funding_rate": state.get("funding_rate"),
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
    return {
        "trades": engine.portfolio.get_recent_trades(limit),
        "total": len(engine.portfolio.trade_history),
    }


@router.get("/portfolio")
async def get_portfolio():
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    tickers = engine.last_market_data.get("tickers", {})
    price = next(iter(tickers.values()), {}).get("last")
    return engine.portfolio.get_state(price)


@router.get("/performance")
async def get_performance():
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return {
        "signal_performance": engine.portfolio.get_signal_performance(),
        "decision_memory": engine.portfolio.decision_memory,
        "risk_status": engine.risk.get_status(),
    }


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
    price = next(iter(tickers.values()), {}).get("last")
    if not price:
        raise HTTPException(status_code=400, detail="No price data available")

    decision = {
        "action": body.action.upper(),
        "confidence": 1.0,
        "amount_pct": body.amount_pct,
        "reason": "Manual override by user",
        "key_signals": ["manual_trade"],
        "risk_level": "MEDIUM",
        "rr_ratio": None,
    }
    trade = await engine._execute_trade(decision, price)
    if trade is None:
        raise HTTPException(status_code=400, detail="Trade not executed (risk check or no holdings)")
    return {"trade": trade, "portfolio": engine.portfolio.get_state(price)}


@router.get("/decisions")
async def get_decisions():
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return {
        "last_decision": engine.last_decision,
        "memory": engine.portfolio.decision_memory,
    }


@router.get("/memory")
async def get_memory():
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    mg = engine.memory_graph
    return {
        "summary": mg.get_memory_summary(),
        "regime_performance": mg.get_regime_performance(),
        "best_signal_combos": mg.get_best_signal_combos(),
        "anti_patterns": mg.get_anti_patterns(),
        "time_performance": mg.get_time_performance(),
        "confluence_performance": mg.get_confluence_performance(),
    }
