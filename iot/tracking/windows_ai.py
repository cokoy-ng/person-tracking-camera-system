"""Ubicación del entorno de IA en el disco local de Windows."""
import os
from pathlib import Path


def python_path():
    configured = os.environ.get('CAMERA_AI_PYTHON')
    if configured:
        return Path(configured)
    candidates = list(Path('/mnt/c/Users').glob('*/AppData/Local/camera-ai/venv/Scripts/python.exe'))
    if len(candidates) != 1:
        raise RuntimeError('Ejecuta python3 setup_ai.py o indica CAMERA_AI_PYTHON con una ruta /mnt/c/.../python.exe.')
    return candidates[0]
