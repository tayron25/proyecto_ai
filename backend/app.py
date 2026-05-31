from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.session import GameSession

ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"

app = FastAPI(title="Consola Multijuegos API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.websocket("/ws/game")
async def game_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    session = GameSession()
    try:
        while True:
            payload = await websocket.receive_json()
            response = session.handle(payload)
            await websocket.send_json(response)
    except WebSocketDisconnect:
        pass
    finally:
        session.close()
