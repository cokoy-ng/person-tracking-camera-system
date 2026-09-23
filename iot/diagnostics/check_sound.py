"""Diagnóstico acotado de D4 y del estado lógico de D3, sin cámara."""
import argparse
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "host"))
from serial_bridge import USB  # noqa: E402


def main():
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='COM3')
    parser.add_argument('--seconds', type=int, default=40)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 300:
        parser.error('--seconds debe estar entre 1 y 300')
    usb = USB(args.port)
    try:
        usb.request('LIGHT PING')
        usb.request('LIGHT HOLD 30')
        usb.request('SOUND CHANGE')
        print('PRUEBA LISTA: una palmada enciende; espera 2 s y haz tres palmadas a ritmo de 0.3-0.7 s para apagar.', flush=True)
        print('Sin cámara ni órdenes LIGHT PERSON; solo el sonido puede renovar la luz.', flush=True)
        start = time.monotonic()
        previous = previous_light = None
        samples = {'LOW': 0, 'HIGH': 0}
        changes = 0
        seen_on = False
        previous_stats = None
        while time.monotonic() - start < args.seconds:
            level = usb.request('SOUND READ').split()[-1]
            state = usb.request('LIGHT STATE').split()[-1]
            stats = usb.request('SOUND STATS')
            if stats != previous_stats:
                print(f'{time.monotonic() - start:.1f}s {stats} (ruidos reconocidos / triples)', flush=True)
                previous_stats = stats
            samples[level] += 1
            seen_on |= state == 'ON'
            if level != previous:
                if previous is not None:
                    changes += 1
                print(f'{time.monotonic() - start:.1f}s D4={level}', flush=True)
                previous = level
            if state != previous_light:
                print(f'{time.monotonic() - start:.1f}s D3={state}', flush=True)
                previous_light = state
            time.sleep(.02)
        print(f'RESULTADO: muestras={samples}, cambios observados={changes}, D3 encendido={seen_on}', flush=True)
        print('El muestreo USB puede perder pulsos breves; el estado D3 lo decide Arduino localmente.', flush=True)
    finally:
        usb.close()
        print('Puerto liberado; sonido autónomo habilitado con espera de 30 s.', flush=True)


if __name__ == '__main__':
    main()
