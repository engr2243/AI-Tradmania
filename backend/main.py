import asyncio
import logging
import sys
import os

# Add backend dir to path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import HOST, PORT
from trading.engine import TradingEngine
from api.routes import router, set_engine
from api.websocket import manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

engine: TradingEngine = None


async def broadcast_update(state: dict):
    await manager.broadcast({"type": "state_update", "data": state})


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    engine = TradingEngine(on_update=broadcast_update)
    set_engine(engine)
    try:
        await engine.start()
        logger.info("Trading engine started successfully")
    except Exception as e:
        logger.error(f"Failed to start trading engine: {e}")
    yield
    if engine:
        await engine.stop()


app = FastAPI(
    title="AI-Tradmania",
    description="Real-time AI crypto trading bot powered by Claude",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send current state immediately on connect
        if engine:
            state = engine.get_full_state()
            await manager.send_personal(websocket, {"type": "state_update", "data": state})

        # Keep connection alive, listen for client messages
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # Echo back ping/pong
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_text('{"type":"heartbeat"}')
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "engine_running": engine.running if engine else False,
        "ws_clients": len(manager.active),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)
