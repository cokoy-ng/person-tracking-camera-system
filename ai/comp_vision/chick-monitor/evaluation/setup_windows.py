"""Prepara un entorno Windows aislado y descarga el modelo de revisión fija."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import venv

ROOT = Path(__file__).resolve().parent.parent


def main():
    if sys.platform != 'win32':
        raise RuntimeError('Ejecutar con Python 3.12 de Windows')
    destination = Path(os.environ['LOCALAPPDATA']) / 'chick-monitor' / 'venv'
    python = destination / 'Scripts/python.exe'
    if not python.exists():
        print('Creando entorno aislado:', destination, flush=True)
        venv.create(destination, with_pip=True)
    subprocess.run([str(python), '-m', 'pip', 'install', 'torch==2.6.0', 'torchvision==0.21.0',
                    '--index-url', 'https://download.pytorch.org/whl/cpu'], check=True)
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements-windows.txt')], check=True)
    manifest = json.loads((ROOT / 'models/provenance.json').read_text(encoding='utf-8'))
    model = ROOT / 'models' / manifest['file']
    if not model.exists():
        temporary = model.with_suffix('.download')
        print('Descargando modelo de revisión fija…', flush=True)
        urllib.request.urlretrieve(manifest['url'], temporary)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != manifest['sha256']:
            raise RuntimeError('El modelo descargado no coincide con SHA256 esperado')
        temporary.replace(model)
    if hashlib.sha256(model.read_bytes()).hexdigest() != manifest['sha256']:
        raise RuntimeError('El modelo local no coincide con SHA256 esperado')
    print('Entorno y modelo verificados:', python, flush=True)


if __name__ == '__main__':
    main()
