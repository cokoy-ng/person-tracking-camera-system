"""API de temperatura y humedad: lee el DHT11 por el puerto serie del Arduino
y lo expone por HTTP y WebSocket para el frontend. Se ejecuta con el Python de
Windows porque necesita abrir el puerto COM directamente."""
import asyncio
import os
import sys
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "iot" / "host"))
from serial_bridge import USB  # noqa: E402

POLL_SECONDS = 2.5
HISTORY_SIZE = 120

app = FastAPI(title="Temperatura y humedad")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

state = {"usb": None, "latest": None, "history": [], "clients": set()}


def read_once():
    response = state["usb"].request("TEMP READ")
    if response == "ERR TEMP":
        return {"ok": False, "timestamp": time.time()}
    _, _, temperature, humidity = response.split()
    return {
        "ok": True,
        "temperature": int(temperature),
        "humidity": int(humidity),
        "timestamp": time.time(),
    }


async def poll_loop():
    loop = asyncio.get_event_loop()
    while True:
        try:
            reading = await loop.run_in_executor(None, read_once)
        except Exception as exc:
            reading = {"ok": False, "error": str(exc), "timestamp": time.time()}
        state["latest"] = reading
        state["history"] = (state["history"] + [reading])[-HISTORY_SIZE:]
        stale = set()
        for ws in state["clients"]:
            try:
                await ws.send_json(reading)
            except Exception:
                stale.add(ws)
        state["clients"] -= stale
        await asyncio.sleep(POLL_SECONDS)


@app.on_event("startup")
async def startup():
    port = os.environ.get("ARDUINO_PORT") or None
    state["usb"] = USB(port)
    asyncio.create_task(poll_loop())


@app.on_event("shutdown")
async def shutdown():
    if state["usb"]:
        state["usb"].close()


@app.get("/api/temperature")
def get_temperature():
    return state["latest"] or {"ok": False, "timestamp": time.time()}


@app.get("/api/temperature/history")
def get_history():
    return state["history"]


@app.websocket("/ws/temperature")
async def ws_temperature(websocket: WebSocket):
    await websocket.accept()
    state["clients"].add(websocket)
    if state["latest"]:
        await websocket.send_json(state["latest"])
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        state["clients"].discard(websocket)
