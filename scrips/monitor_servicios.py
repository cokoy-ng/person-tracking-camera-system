"""Arranca/reutiliza backend Windows y verifica telemetría sin actuar sobre Arduino."""
import argparse
import base64
import hashlib
import socket
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
API = 'http://127.0.0.1:8000/api/brooder'


def reading():
    with urllib.request.urlopen(API, timeout=3) as response:
        data = json.load(response)
    if not isinstance(data, dict) or 'ok' not in data or 'timestamp' not in data:
        raise ValueError('El puerto 8000 no devuelve la API esperada del criadero')
    return data


def check_websocket():
    """Comprueba el handshake y una muestra JSON por el canal usado por React."""
    key = base64.b64encode(os.urandom(16)).decode()
    with socket.create_connection(('127.0.0.1', 8000), timeout=12) as sock:
        request = ('GET /ws/temperature HTTP/1.1\r\nHost: localhost:8000\r\n'
                   'Upgrade: websocket\r\nConnection: Upgrade\r\n'
                   f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n'
                   'Origin: http://localhost:5173\r\n\r\n')
        sock.sendall(request.encode('ascii'))
        stream = sock.makefile('rb')
        status = stream.readline()
        headers = {}
        while True:
            line = stream.readline()
            if line in (b'\r\n', b''):
                break
            name, value = line.decode().split(':', 1)
            headers[name.lower()] = value.strip()
        expected = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
        if b' 101 ' not in status or headers.get('sec-websocket-accept') != expected:
            raise ValueError('WebSocket no aceptó la conexión')
        def exact(size):
            data = stream.read(size)
            if len(data) != size:
                raise ValueError('WebSocket cerrado antes de recibir una lectura')
            return data
        first, second = exact(2)
        if first & 15 != 1 or second & 128:
            raise ValueError('WebSocket no envió una trama de texto válida')
        length = second & 127
        if length == 126:
            length = int.from_bytes(exact(2), 'big')
        elif length == 127:
            length = int.from_bytes(exact(8), 'big')
        if length > 1048576:
            raise ValueError('Trama WebSocket demasiado grande')
        data = json.loads(exact(length))
        if not data.get('ok') or not data.get('serial_connected') or not 0 <= time.time() - data.get('timestamp', 0) <= 8:
            raise ValueError('WebSocket conectado pero sin una lectura reciente válida')
        # Cierre normal, trama enmascarada de cliente con código 1000.
        sock.sendall(b'\x88\x82\x00\x00\x00\x00\x03\xe8')
    print('WebSocket verificado: muestra real recibida en /ws/temperature.', flush=True)


def backend_processes():
    """Solo uvicorn main:app de este backend; no mata por número de puerto."""
    backend = str(ROOT / 'backend').replace('/', chr(92)).lower().replace("'", "''")
    script = ("$ErrorActionPreference='Stop'; @(Get-CimInstance Win32_Process | "
              "Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine -and $_.CommandLine.Contains('uvicorn') "
              "-and $_.CommandLine.Contains('main:app') -and "
              f"$_.CommandLine.Replace([char]47, [char]92).ToLower().Contains('{backend}') "
              "} | Select-Object ProcessId) | ConvertTo-Json -Compress")
    output = subprocess.check_output(['powershell.exe', '-NoProfile', '-Command', script], text=True).strip()
    result = json.loads(output) if output else []
    return result if isinstance(result, list) else [result]


def stop_backend():
    processes = backend_processes()
    for process in processes:
        pid = int(process['ProcessId'])
        subprocess.run(['powershell.exe', '-NoProfile', '-Command',
                        f"$p=Get-Process -Id {pid} -ErrorAction SilentlyContinue; if ($p) {{ Stop-Process -Id {pid} -ErrorAction Stop }}"], check=True)
        print(f'Backend del proyecto detenido: PID {pid}.', flush=True)
    for _ in range(10):
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1', 8000)) != 0:
                print('Backend: DETENIDO; puerto 8000 libre.', flush=True)
                return
        time.sleep(1)
    raise RuntimeError('El puerto 8000 sigue ocupado. No se terminaron procesos ajenos al proyecto.')


def show_status():
    try:
        data = reading()
    except (OSError, ValueError) as exc:
        print('Backend: NO DISPONIBLE —', exc, flush=True)
        return 1
    fresh = 0 <= time.time() - data['timestamp'] <= 8
    print('Backend: ARRIBA — http://localhost:8000', flush=True)
    print('Arduino:', 'CONECTADO' if data.get('serial_connected') and fresh else 'SIN CONEXIÓN RECIENTE', flush=True)
    print(f"Sensor: {'VÁLIDO' if data.get('ok') and fresh else 'SIN LECTURA VÁLIDA'}; temperatura {data.get('temperature')} °C; humedad {data.get('humidity')} % HR.", flush=True)
    print(f"Firmware: {data.get('firmware_reported')}; pausa: {data.get('stopped')}; calefacción: {data.get('heater')}; bomba: {data.get('controls', {}).get('humidifier', {}).get('on')}.", flush=True)
    return 0 if data.get('ok') and data.get('serial_connected') and data.get('outputs_valid') and fresh else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--estado', action='store_true')
    modes.add_argument('--stop', action='store_true')
    parser.add_argument('--port', help='Puerto explícito, por ejemplo COM6; por defecto detecta Arduino')
    parser.add_argument('--watch', action='store_true', help='Seguir comprobando la conexión cada 5 segundos')
    args = parser.parse_args()
    if sys.platform != 'win32':
        raise RuntimeError('Este auxiliar debe ejecutarse con Python de Windows desde levantar_todo.sh')
    if args.estado:
        sys.exit(show_status())
    if args.stop:
        stop_backend()
        return
    runtime = ROOT / '.runtime'
    runtime.mkdir(exist_ok=True)
    try:
        reading()
        print('Backend existente: se reutiliza sin abrir otro lector serie.', flush=True)
    except (OSError, ValueError):
        # Si 8000 ya está ocupado, no lanzar otro lector contra el mismo Arduino.
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1', 8000)) == 0:
                raise RuntimeError('Puerto 8000 ocupado por una API no reconocida; no se inicia otro backend')
        sys.path.insert(0, str(ROOT / 'iot' / 'host'))
        from serial_bridge import serial
        from serial.tools import list_ports
        ports = list(list_ports.comports())
        if args.port:
            matches = [p for p in ports if p.device.upper() == args.port.upper()]
        else:
            matches = [p for p in ports if 'arduino' in p.description.lower() or p.vid == 0x2341]
        if len(matches) != 1:
            raise RuntimeError('No se detectó un Arduino único. Puertos: ' + ', '.join(p.device + ' ' + p.description for p in ports) + '. Usa --port COMx')
        port = matches[0].device
        env = dict(os.environ, ARDUINO_PORT=port)
        with (runtime / 'backend.log').open('ab') as log:
            proc = subprocess.Popen(
                [sys.executable, '-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000', '--app-dir', str(ROOT / 'backend')],
                env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        print(f'Backend iniciado: PID {proc.pid}, Arduino {port}.', flush=True)
    print('Comprobando lecturas nuevas durante al menos 15 segundos…', flush=True)
    started = time.monotonic()
    deadline = started + 45
    consecutive = 0
    stable_since = None
    last_stamp = None
    last_error = 'Todavía sin datos'
    while time.monotonic() < deadline:
        try:
            data = reading()
            if not data.get('serial_connected') or not data.get('outputs_valid'):
                raise ValueError(data.get('error') or 'Sin conexión serie o estado de salidas válido')
            if not data.get('ok'):
                raise ValueError('Arduino conectado, pero sensor/ciclo sin lectura válida')
            if not 0 <= time.time() - data['timestamp'] <= 8:
                raise ValueError('Lectura caducada')
            if stable_since is None:
                stable_since = time.monotonic()
            if data['timestamp'] != last_stamp:
                consecutive += 1
                last_stamp = data['timestamp']
            if consecutive >= 5 and time.monotonic() - stable_since >= 15:
                break
        except (OSError, ValueError, KeyError) as exc:
            consecutive = 0
            stable_since = None
            last_stamp = None
            last_error = str(exc)
        time.sleep(2)
    else:
        raise RuntimeError(f'No se confirmó estabilidad: {last_error}. Revisa .runtime/backend.log y el cable/sensor. Los servicios quedan disponibles para diagnóstico.')
    check_websocket()
    print(f"Conexión estable durante la prueba: {consecutive} lecturas nuevas; {data['temperature']} °C, {data['humidity']} % HR; ciclo {data.get('cycle', {}).get('id')}.", flush=True)
    print(f"Firmware: {data.get('firmware_reported')}; pausa: {data.get('stopped')}; calefacción: {data.get('heater')}; bomba: {data.get('controls', {}).get('humidifier', {}).get('on')}.", flush=True)
    print('Dashboard: http://localhost:5173/ — servicios permanecen activos. No se enviaron órdenes de actuación.', flush=True)
    if args.watch:
        watch_started = time.time()
        print('Vigilancia activa; Ctrl+C termina la vigilancia y deja los servicios activos.', flush=True)
        while True:
            time.sleep(5)
            stop_marker = runtime / 'monitor.stop'
            if stop_marker.exists() and stop_marker.stat().st_mtime >= watch_started:
                print('Vigilancia terminada por --stop.', flush=True)
                return
            try:
                data = reading()
                valid = data.get('ok') and data.get('serial_connected') and data.get('outputs_valid') and 0 <= time.time() - data['timestamp'] <= 8
                print(time.strftime('%H:%M:%S'), 'OK' if valid else 'SIN LECTURA VÁLIDA', data.get('temperature'), '°C', data.get('humidity'), '% HR', data.get('error') or '', flush=True)
            except (OSError, ValueError, KeyError) as exc:
                print('Conexión no disponible:', exc, flush=True)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nVigilancia terminada; servicios siguen activos.')
    except Exception as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)
