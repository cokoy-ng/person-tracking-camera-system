"""Dashboard del criadero: telemetría y mandos auditados mediante un único lector serie."""
import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
import sys
import time
import queue
import uuid
from concurrent.futures import Future
from pydantic import BaseModel, Field, model_validator
from typing import Literal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from brooder_stream import Telemetry, REMAPPED_FIRMWARES
from event_history import EventHistory
from configuration_audit import software_snapshot

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'iot' / 'host'))
from serial_bridge import serial

HISTORY_SIZE = 120
state = {'serial': None, 'latest': None, 'history': [], 'clients': set()}
telemetry = Telemetry()
history_path = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'camera-brooder' / 'events.sqlite3'
event_history = EventHistory(history_path, archive_dir=Path(__file__).resolve().parent / 'data',
    software=software_snapshot(Path(__file__).resolve().parent.parent, os.environ.get('ARDUINO_PORT','COM3')))
commands = queue.Queue(maxsize=8)
OUTPUT_NAMES = ('heater', 'humidifier', 'exhaust', 'intake', 'alarm')


def close_serial():
    if state['serial'] is not None:
        state['serial'].close()
        state['serial'] = None


def command_ack(command):
    if command.startswith('!'): return f'OK CONTROL {command}'
    action = command[1]
    return {'Z':'OK SERVO TEST', 'S':'OK STOP', 'A':'OK AUTO', 'B':'OK DOOR OPEN', 'D':'OK DOOR CLOSE', 'X':'OK DOOR STOP', 'O':'OK REFERENCE OPEN', 'C':'OK REFERENCE CLOSED'}.get(action, f'OK CYCLE {action}')


def read_once():
    global telemetry
    if state['serial'] is None:
        port = serial.Serial(port=None, baudrate=115200, timeout=0.5, write_timeout=2)
        # Configurar antes de abrir: no reiniciar ni referenciar la puerta.
        port.dtr = False
        port.rts = False
        port.port = os.environ.get('ARDUINO_PORT', 'COM3')
        port.open()
        port.write(b'~?3F\n')  # Identidad/estado, sin activar salidas.
        state['serial'] = port
        telemetry = Telemetry()
    deadline = time.monotonic() + 7
    pending = None
    try:
        pending = commands.get_nowait()
    except queue.Empty:
        pass
    confirmed = False
    attempts = 0
    next_send = 0
    if pending:
        char, expires, future = pending
        if future.cancelled() or time.monotonic() > expires:
            pending = None
    while time.monotonic() < deadline:
        if pending and not confirmed and attempts < (1 if pending[0] in ('~Z5A','~B42','~D44') else 3) and time.monotonic() >= next_send:
            if pending[2].cancelled():
                pending = None
            else:
                char = pending[0]
                state['serial'].write(f'{char}\n'.encode('ascii'))
                attempts += 1
                next_send = time.monotonic()+1.5
        line = state['serial'].readline().decode('ascii', errors='replace').strip()
        if pending and line == command_ack(pending[0]):
            confirmed = True
        # ERR FRAME has no request identity: an incomplete prior frame must not
        # reject a command that may still receive its ACK. Missing ACK times out.
        if pending and line.startswith('ERR') and line != 'ERR FRAME':
            if not pending[2].done(): pending[2].set_exception(ValueError(line))
            pending = None
        reading = telemetry.feed(line)
        if reading is not None:
            if pending and not confirmed:
                continue
            if pending and not pending[2].done():
                pending[2].set_result(reading)
            return reading
    if pending and not pending[2].done():
        pending[2].set_exception(TimeoutError('Arduino no confirmó el mando'))
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
        try:
            await asyncio.to_thread(event_history.record, reading)
            state['history_error'] = None
        except Exception as exc:
            state['history_error'] = str(exc)
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
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'], allow_methods=['GET','POST'], allow_headers=['Content-Type'])


class ControlRequest(BaseModel):
    output: Literal['heater','humidifier','exhaust','intake','alarm']
    mode: Literal['auto','off','on']
    duration_seconds: int = Field(default=60, ge=0, le=86400, strict=True)


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    if request.url.path in ('/api/control', '/api/device'):
        try:
            await asyncio.to_thread(event_history.audit_command,uuid.uuid4().hex,'rejected',None,None,None,
                                    state['latest'],reason='Petición inválida: salida, modo o duración no admitidos',http_status=422)
        except Exception as error:
            state['history_error']=str(error)
    return JSONResponse(status_code=422,content={'detail':'Parámetros inválidos; revisa salida, modo, duración o paginación'})


@app.post('/api/control')
async def control_output(request: ControlRequest):
    request_id=uuid.uuid4().hex
    before=state['latest'] or {}
    seconds=request.duration_seconds if request.mode!='auto' else 0
    # Persist the intention before sending: never operate without a recorded request.
    try:
        await asyncio.to_thread(event_history.audit_command,request_id,'requested',request.output,
                                request.mode,seconds,before)
    except Exception as exc:
        state['history_error']=str(exc)
        raise HTTPException(503,'No se pudo guardar la solicitud; no se envió la orden')
    try:
        reading,actual=await execute_control(request)
    except HTTPException as exc:
        status='unconfirmed' if exc.status_code in (502,504) else 'rejected'
        try:
            await asyncio.to_thread(event_history.audit_command,request_id,status,request.output,
                request.mode,seconds,before,after=state['latest'],reason=str(exc.detail),http_status=exc.status_code)
        except Exception as error: state['history_error']=str(error)
        raise
    error=None
    try:
        await asyncio.to_thread(event_history.audit_command,request_id,'confirmed',request.output,
                                request.mode,seconds,before,after=reading,http_status=200)
    except Exception as exc:
        error='Orden confirmada; no se pudo completar su registro. Revisa el almacenamiento.'
        state['history_error']=str(exc)
    return {'confirmed': True, 'control': actual, 'request_id':request_id, 'history_error':error}


async def execute_control(request):
    latest = state['latest'] or {}
    if not latest.get('serial_connected') or time.time()-latest.get('timestamp',0)>6 or not latest.get('controls'):
        raise HTTPException(409, 'Sin conexión actual con firmware de control manual')
    if latest.get('firmware_reported') in REMAPPED_FIRMWARES and request.output == 'intake':
        raise HTTPException(409, 'La segunda salida de aire fue retirada; A1–A5 están libres')
    if request.output=='humidifier' and request.mode=='auto':
        raise HTTPException(409, 'La motobomba D7 es exclusivamente manual: elige Encender o Apagar')
    index = OUTPUT_NAMES.index(request.output)
    mode = ('auto','off','on').index(request.mode)
    payload = f'!{index}{mode}{request.duration_seconds if mode else 0}'
    checksum = 0
    for byte in payload.encode('ascii'): checksum ^= byte
    command = f'{payload}*{checksum:02X}'
    future = Future()
    try:
        commands.put_nowait((command, time.monotonic()+10, future))
    except queue.Full:
        raise HTTPException(429, 'Hay mandos pendientes; espera la confirmación')
    try:
        reading = await asyncio.wait_for(asyncio.wrap_future(future), timeout=12)
    except Exception:
        future.cancel()
        raise HTTPException(504, 'No se confirmó la orden; revisa el estado actual')
    actual = (reading.get('controls') or {}).get(request.output)
    if not actual or actual['mode'] != request.mode:
        raise HTTPException(502, 'El Arduino no confirmó el modo solicitado')
    return reading,actual


class DeviceRequest(BaseModel):
    action: Literal['servo_cycle', 'stop', 'resume', 'cycle', 'door_open', 'door_close', 'door_stop', 'door_reference_open', 'door_reference_closed']
    cycle: int | None = Field(default=None, ge=1, le=4, strict=True)

    confirmed_position: bool = Field(default=False, strict=True)

    @model_validator(mode='after')
    def check_cycle(self):
        if (self.action == 'cycle') != (self.cycle is not None):
            raise ValueError('Indica ciclo solo para seleccionar un ciclo')
        if self.action.startswith('door_reference_') and not self.confirmed_position:
            raise ValueError('Confirma físicamente la posición de puerta antes de referenciar')
        if self.confirmed_position and not self.action.startswith('door_reference_'):
            raise ValueError('Confirmación de posición solo para referencia de puerta')
        return self


async def execute_device(request):
    latest = state['latest'] or {}
    if (not latest.get('serial_connected') or time.time()-latest.get('timestamp',0)>6
            or latest.get('firmware_reported') not in REMAPPED_FIRMWARES):
        raise HTTPException(409, 'Sin conexión actual con el firmware actualizado')
    if request.action == 'cycle' and latest.get('firmware_reported') in ('BROODER_14_PHYSICAL_CYCLES','BROODER_15_AUTO_CYCLES','BROODER_16_MANUAL_PUMP'):
        raise HTTPException(409, 'El ciclo se selecciona moviendo la señal del sensor a D2, D3, D4 o D5')
    if request.action == 'servo_cycle' and (latest.get('servo') or {}).get('running'):
        raise HTTPException(409, 'El servo ya está ejecutando un ciclo')
    if request.action == 'resume' and not latest.get('ok'):
        raise HTTPException(409, 'Selecciona un ciclo y espera lecturas válidas antes de reanudar')
    if request.action.startswith('door_'):
        if latest.get('firmware_reported') not in ('BROODER_13_MANUAL_DOOR','BROODER_14_PHYSICAL_CYCLES','BROODER_15_AUTO_CYCLES','BROODER_16_MANUAL_PUMP') or not latest.get('door_control'):
            raise HTTPException(409, 'La puerta requiere el firmware de control manual actualizado')
        if request.action != 'door_stop' and (latest.get('door_control') or {}).get('running'):
            raise HTTPException(409, 'Detén la puerta antes de cambiar dirección o referencia')
        if request.action in ('door_open','door_close') and not latest.get('referenced'):
            raise HTTPException(409, 'Confirma primero si la puerta está totalmente abierta o cerrada')
    char = {'servo_cycle':'Z', 'stop':'S', 'resume':'A', 'door_open':'B', 'door_close':'D', 'door_stop':'X', 'door_reference_open':'O', 'door_reference_closed':'C'}.get(request.action, str(request.cycle))
    command = f'~{char}{ord(char):02X}'
    future = Future()
    try:
        commands.put_nowait((command, time.monotonic()+10, future))
    except queue.Full:
        raise HTTPException(429, 'Hay mandos pendientes; espera la confirmación')
    try:
        reading = await asyncio.wait_for(asyncio.wrap_future(future), timeout=12)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    except Exception:
        future.cancel()
        raise HTTPException(504, 'No se confirmó la orden; revisa el estado antes de repetir')
    if request.action == 'stop' and not reading.get('stopped'):
        raise HTTPException(502, 'No se confirmó la parada')
    if request.action == 'resume' and reading.get('stopped'):
        raise HTTPException(502, 'No se confirmó la reanudación')
    if request.action == 'cycle' and reading.get('requested_cycle') != request.cycle:
        raise HTTPException(502, 'No se confirmó el ciclo solicitado')
    if request.action == 'servo_cycle' and not (reading.get('servo') or {}).get('running'):
        raise HTTPException(502, 'No se confirmó el inicio del servo')
    if request.action.startswith('door_'):
        if request.action == 'door_stop' and (reading.get('door_control') or {}).get('running'):
            raise HTTPException(502, 'No se confirmó la parada de puerta')
        if request.action in ('door_reference_open','door_reference_closed'):
            expected=49152 if request.action=='door_reference_closed' else 0
            if not reading.get('referenced') or reading.get('position')!=expected:
                raise HTTPException(502, 'No se confirmó la referencia de puerta')
        if request.action in ('door_open','door_close'):
            expected=49152 if request.action=='door_close' else 0
            if not reading.get('referenced') or reading.get('target')!=expected:
                raise HTTPException(502, 'No se confirmó el destino de puerta')
    return reading


@app.post('/api/device')
async def control_device(request: DeviceRequest):
    request_id = uuid.uuid4().hex
    before = state['latest'] or {}
    output = 'door' if request.action.startswith('door_') else 'servo' if request.action == 'servo_cycle' else 'cycle' if request.action == 'cycle' else 'system'
    mode = str(request.cycle) if request.action == 'cycle' else request.action
    try:
        await asyncio.to_thread(event_history.audit_command,request_id,'requested',output,mode,None,before)
    except Exception as exc:
        state['history_error'] = str(exc)
        raise HTTPException(503, 'No se pudo guardar la solicitud; no se envió la orden')
    try:
        reading = await execute_device(request)
    except HTTPException as exc:
        try:
            await asyncio.to_thread(event_history.audit_command,request_id,
                'unconfirmed' if exc.status_code in (502,504) else 'rejected',output,mode,None,before,
                after=state['latest'],reason=str(exc.detail),http_status=exc.status_code)
        except Exception as error: state['history_error'] = str(error)
        raise
    error = None
    try:
        await asyncio.to_thread(event_history.audit_command,request_id,'confirmed',output,mode,None,before,
                                after=reading,http_status=200)
    except Exception as exc:
        error = 'Orden confirmada; no se pudo completar su registro.'
        state['history_error'] = str(exc)
    return {'confirmed':True, 'state':reading, 'request_id':request_id, 'history_error':error}


@app.get('/api/temperature')
@app.get('/api/brooder')
def get_latest():
    return state['latest'] or {'ok': False, 'outputs_valid': False, 'timestamp': time.time()}


@app.get('/api/temperature/history')
def get_history():
    return state['history']


@app.get('/api/events')
def get_events(page: int = Query(1,ge=1), page_size: int = Query(25,ge=1,le=100),
               kind: Literal['all','reading','output','alarm','connection','sensor','cycle','system','configuration','command'] = 'all',
               snapshot_id: int | None = Query(None,ge=0)):
    return {**event_history.page(page,page_size,kind,snapshot_id), 'error':state.get('history_error')}


@app.get('/api/history/{dataset}.csv')
def export_history(dataset: Literal['events','readings','configurations'],
                   kind: Literal['all','reading','output','alarm','connection','sensor','cycle','system','configuration','command'] = 'all'):
    return StreamingResponse(event_history.export_csv(dataset,kind),media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition':f'attachment; filename="brooder_{dataset}_{time.strftime("%Y%m%d")}.csv"',
                 'Cache-Control':'no-store'})


@app.get('/api/configurations/{config_id}')
def get_configuration(config_id: int):
    configuration=event_history.configuration(config_id)
    if configuration is None: raise HTTPException(404,'Configuración no encontrada')
    return JSONResponse(configuration,headers={'Content-Disposition':f'attachment; filename="configuration_{config_id}.json"'})


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
