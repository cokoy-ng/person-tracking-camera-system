"""Entrada integrada para la cámara USB y servo del proyecto vecino perip."""
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    perip = Path(__file__).resolve().parent.parent / 'perip'
    sys.path.insert(0, str(perip))
    runpy.run_path(str(perip / 'tracking.py'), run_name='__main__')
