"""Captura USB para el backend web, sin ventanas ni acceso al Arduino."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / '.runtime'
STATUS = RUNTIME / 'camara.json'
STOP = RUNTIME / 'camara.stop'
FRAME = RUNTIME / 'camara.jpg'


def processes():
    paths = [str(Path(__file__).resolve()), str(ROOT / 'iot/tracking/camera.py')]
    # Match full script paths, never an arbitrary Python.
    clauses = ["$_.CommandLine.Replace([char]47,[char]92).ToLower().Contains('" +
               path.replace('/', '\\').lower().replace("'", "''") + "')" for path in paths]
    script = ("@(Get-CimInstance Win32_Process | Where-Object { "
              "($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine -and (" +
              ' -or '.join(clauses) + ") } | Select-Object ProcessId) | ConvertTo-Json -Compress")
    output = subprocess.check_output(['powershell.exe', '-NoProfile', '-Command', script], text=True).strip()
    data = json.loads(output) if output else []
    return [int(item['ProcessId']) for item in (data if isinstance(data, list) else [data])
            if int(item['ProcessId']) != os.getpid()]


def state():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8766/status', timeout=2) as response:
            data = json.load(response)
        if data.get('ok') and data.get('transport') == 'memory-v1' and 0 <= time.time() - data['timestamp'] <= 3:
            return data
    except (OSError, ValueError, KeyError):
        pass
    return None


def show_status(pids=None):
    pids = processes() if pids is None else pids
    data = state()
    if data and data.get('pid') in pids:
        print(f"Cámara: ARRIBA — {data['name']}; {data['width']} x {data['height']}; "
              f"{data['fps']} FPS de captura; video en el dashboard.", flush=True)
        return True
    print('Cámara: SIN IMÁGENES RECIENTES' if pids else 'Cámara: DETENIDA', flush=True)
    return False


def stop_camera():
    pids = processes()
    STOP.touch()  # Compatibility with the previous file-based worker.
    try:
        request = urllib.request.Request('http://127.0.0.1:8766/stop', method='POST')
        with urllib.request.urlopen(request, timeout=2):
            pass
    except OSError:
        pass
    # The managed preview releases the USB itself; legacy previews need termination.
    for _ in range(5):
        remaining = processes()
        if not set(pids) & set(remaining):
            break
        time.sleep(0.5)
    else:
        for pid in set(pids) & set(remaining):
            subprocess.run(['powershell.exe', '-NoProfile', '-Command',
                            f'$p=Get-Process -Id {pid} -ErrorAction SilentlyContinue; '
                            f'if ($p) {{ Stop-Process -Id {pid} -ErrorAction Stop }}; exit 0'], check=True)
    if processes():
        raise RuntimeError('La vista de cámara sigue ejecutándose')
    STATUS.unlink(missing_ok=True)
    FRAME.unlink(missing_ok=True)
    print('Cámara: DETENIDA; webcam liberada.', flush=True)


def preview():
    sys.path.insert(0, str(ROOT / 'iot/tracking'))
    from camera_capture import serve_capture
    serve_capture()


def start_camera():
    pids = processes()
    if show_status(pids) and (state() or {}).get('frame_api') == 1:
        print('Vista existente: se reutiliza.', flush=True)
        return
    if pids:
        print('Reemplazando vista anterior por la vista integrada…', flush=True)
        stop_camera()
    python = ROOT / 'iot/tracking/.venv-win/Scripts/python.exe'
    if not python.is_file():
        raise RuntimeError('Falta el entorno Windows de cámara iot/tracking/.venv-win')
    STOP.unlink(missing_ok=True)
    STATUS.unlink(missing_ok=True)
    started = time.time()
    with (RUNTIME / 'camara.log').open('ab') as log:
        child = subprocess.Popen([str(python), '-u', str(Path(__file__).resolve()), '--preview'],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError('La vista de cámara terminó. Revisa .runtime/camara.log')
        data = state()
        if data and data['timestamp'] >= started and data.get('frames', 0) >= 5:
            if not show_status():
                raise RuntimeError('No se confirmó el proceso de cámara')
            return
        time.sleep(0.5)
    raise RuntimeError('No se confirmaron imágenes en 45 segundos. Revisa .runtime/camara.log')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--estado', action='store_true')
    modes.add_argument('--stop', action='store_true')
    modes.add_argument('--preview', action='store_true')
    args = parser.parse_args()
    if sys.platform != 'win32':
        raise RuntimeError('Ejecutar con Python de Windows; usar sh/monitoreo_pollitos.sh desde WSL')
    RUNTIME.mkdir(exist_ok=True)
    if args.preview:
        preview()
    elif args.estado:
        return 0 if show_status() else 1
    elif args.stop:
        stop_camera()
    else:
        start_camera()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('ERROR cámara:', exc, file=sys.stderr, flush=True)
        sys.exit(1)
