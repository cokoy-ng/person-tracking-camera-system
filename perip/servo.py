"""Entrada al controlador existente del servo D2 desde perip."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parent.parent / "arduino" / "servo.py"),
                   run_name="__main__")
