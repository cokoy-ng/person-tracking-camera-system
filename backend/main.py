"""Dashboard del criadero: escucha la telemetría, sin ordenar movimientos."""
import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
import sys
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from brooder_stream import Telemetry

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'iot' / 'host'))
from serial_bridge import serial

HISTORY_SIZE = 120
state = {'serial': None, 'latest': None, 'history': [], 'clients': set()}
telemetry = Telemetry()


def close_serial():
    if state['serial'] is not None:
        state['serial'].close()
        state['serial'] = None


def read_once():
    global telemetry
    if state['serial'] is None:
        port = serial.Serial(port=None, baudrate=115200, timeout=0.5, write_timeout=2)
        # Configurar antes de abrir: no reiniciar ni referenciar la puerta.
        port.dtr = False
        port.rts = False
        port.port = os.environ.get('ARDUINO_PORT', 'COM3')
        port.open()
        state['serial'] = port
        telemetry = Telemetry()
    deadline = time.monotonic() + 7
    while time.monotonic() < deadline:
        line = state['serial'].readline().decode('ascii', errors='replace').strip()
        reading = telemetry.feed(line)
        if reading is not None:
            return reading
    raise TimeoutError('Sin telemetría del criadero durante 7 segundos')


async def poll_loop():
    while True:
        try:
            reading = await asyncio.to_thread(read_once)
        except Exception as exc:
            close_serial()
            reading = {'ok': False, 'serial_connected': False, 'outputs_valid': False,
                       'error': str(exc), 'timestamp': time.time()}
        state['latest'] = reading
        state['history'] = (state['history'] + [reading])[-HISTORY_SIZE:]
        for ws in list(state['clients']):
            try:
                await asyncio.wait_for(ws.send_json(reading), timeout=2)
            except Exception:
                state['clients'].discard(ws)
        await asyncio.sleep(0.1 if reading.get('serial_connected') else 2)


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(poll_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    close_serial()  # Cerrar el monitor no envía STOP al control autónomo.


app = FastAPI(title='Criadero · sensores y control', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['GET'], allow_headers=['*'])


@app.get('/api/temperature')
@app.get('/api/brooder')
def get_latest():
    return state['latest'] or {'ok': False, 'outputs_valid': False, 'timestamp': time.time()}


@app.get('/api/temperature/history')
def get_history():
    return state['history']


@app.websocket('/ws/temperature')
async def ws_temperature(websocket: WebSocket):
    await websocket.accept()
    state['clients'].add(websocket)
    try:
        if state['latest']:
            await websocket.send_json(state['latest'])
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        state['clients'].discard(websocket)
