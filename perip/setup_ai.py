"""Instala el entorno Windows de IA sin modificar el entorno de cámara básica."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    if sys.platform != 'linux':
        raise RuntimeError('Ejecuta python3 setup_ai.py desde WSL.')
    configured = os.environ.get('ARDUINO_WINDOWS_PYTHON')
    candidates = [Path(configured)] if configured else list(
        Path('/mnt/c/Users').glob('*/AppData/Local/Programs/Python/Python*/python.exe'))
    if len(candidates) != 1:
        raise RuntimeError('Indica ARDUINO_WINDOWS_PYTHON con la ruta del Python de Windows.')
    def win(path):
        return subprocess.check_output(['wslpath', '-w', str(path)], text=True).strip()
    localappdata = subprocess.check_output([str(candidates[0]), '-c',
        'import os; print(os.environ["LOCALAPPDATA"])'], text=True).strip()
    localpath = subprocess.check_output(['wslpath', '-u', localappdata], text=True).strip()
    env = Path(localpath) / 'camera-ai/venv'
    python = env / 'Scripts/python.exe'
    if not python.exists():
        subprocess.run([str(candidates[0]), '-m', 'venv', win(env)], check=True)
    subprocess.run([str(python), '-m', 'pip', 'install', '-r',
                    win(ROOT.parent / 'emotion-detector/requirements-windows.txt')], check=True)
    print('Listo. Ejecuta python3 tracking.py desde perip.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
