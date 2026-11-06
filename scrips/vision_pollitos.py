"""Inicia, consulta o detiene el análisis visual aislado del criadero."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
WORKER = ROOT / 'ai/comp_vision/chick-monitor/worker.py'
URL = 'http://127.0.0.1:8767'


def state():
    try:
        with urllib.request.urlopen(URL+'/status', timeout=2) as response:
            data = json.load(response)
        if data.get('project') == str(ROOT) and data.get('version') in (1, 2):
            return data
    except (OSError, ValueError):
        pass
    return None


def processes():
    path = str(WORKER).replace('/', '\\').lower().replace("'", "''")
    script = ("@(Get-CimInstance Win32_Process | Where-Object { "
              "($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine -and "
              f"$_.CommandLine.Replace([char]47,[char]92).ToLower().Contains('{path}') "
              "} | Select-Object ProcessId) | ConvertTo-Json -Compress")
    output = subprocess.check_output(['powershell.exe', '-NoProfile', '-Command', script], text=True).strip()
    data = json.loads(output) if output else []
    return [int(item['ProcessId']) for item in (data if isinstance(data, list) else [data])]


def show_status():
    data = state()
    if data and data.get('fresh'):
        print(f"Visión: ACTIVA — {data['count']} aves visibles; {data.get('fps', 0)} FPS IA; "
              f"{data.get('inference_ms')} ms por análisis. Modelo en evaluación.", flush=True)
        return True
    print('Visión:', data.get('status') if data else 'NO DISPONIBLE', flush=True)
    return False


def stop():
    pids = processes()
    if state():
        with urllib.request.urlopen(urllib.request.Request(URL+'/stop', method='POST'), timeout=2):
            pass
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
        raise RuntimeError('No se pudo cerrar el proceso de visión')
    print('Visión: DETENIDA.', flush=True)


def start():
    data = state()
    if show_status() and data and data.get('version') == 2:
        return
    if data and data.get('version') != 2:
        stop()
    python = Path(os.environ.get('CHICK_VISION_PYTHON',
        str(Path(os.environ['LOCALAPPDATA']) / 'chick-monitor/venv/Scripts/python.exe')))
    if not python.is_file():
        raise RuntimeError('Falta el entorno de visión. Ejecuta ai/comp_vision/chick-monitor/evaluation/setup_windows.py con Python de Windows.')
    child = None
    if state() is None:
        if processes():
            raise RuntimeError('Existe un proceso de visión sin servicio disponible. Revisa .runtime/vision.log antes de reiniciar.')
        runtime = ROOT / '.runtime'
        runtime.mkdir(exist_ok=True)
        with (runtime/'vision.log').open('ab') as log:
            child = subprocess.Popen([str(python), '-u', str(WORKER)], stdin=subprocess.DEVNULL,
                stdout=log, stderr=log, cwd=str(WORKER.parent),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    print('Cargando detector y esperando el primer análisis real…', flush=True)
    deadline = time.monotonic()+120
    while time.monotonic() < deadline:
        if child is not None and child.poll() is not None:
            raise RuntimeError('El detector terminó. Revisa .runtime/vision.log')
        data = state()
        if data and data.get('status') == 'error':
            raise RuntimeError(data.get('error') or 'Error cargando el detector')
        if data and data.get('fresh'):
            show_status()
            return
        time.sleep(0.5)
    raise RuntimeError('No se confirmó análisis reciente en 120s. Revisa cámara y .runtime/vision.log')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--estado', action='store_true')
    group.add_argument('--stop', action='store_true')
    args = parser.parse_args()
    if sys.platform != 'win32':
        raise RuntimeError('Usar Python de Windows desde sh/monitoreo_pollitos.sh')
    if args.estado:
        return 0 if show_status() else 1
    if args.stop:
        stop()
    else:
        start()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('ERROR visión:', exc, file=sys.stderr, flush=True)
        sys.exit(1)
