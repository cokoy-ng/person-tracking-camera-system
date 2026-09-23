"""Diagnóstico del DHT11 en A5 (temperatura y humedad), sin cámara."""
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
    parser.add_argument('--seconds', type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 300:
        parser.error('--seconds debe estar entre 1 y 300')
    usb = USB(args.port)
    try:
        print('Leyendo TEMP READ cada 2 s (el DHT11 no responde bien a más frecuencia).', flush=True)
        start = time.monotonic()
        ok = 0
        err = 0
        while time.monotonic() - start < args.seconds:
            response = usb.request('TEMP READ')
            elapsed = time.monotonic() - start
            if response == 'ERR TEMP':
                err += 1
                print(f'{elapsed:.1f}s ERR TEMP (sin respuesta del sensor o checksum inválido)', flush=True)
            else:
                ok += 1
                _, _, temperature, humidity = response.split()
                print(f'{elapsed:.1f}s temperatura={temperature}C humedad={humidity}%', flush=True)
            time.sleep(2)
        print(f'RESULTADO: lecturas ok={ok}, errores={err}', flush=True)
    finally:
        usb.close()
        print('Puerto liberado.', flush=True)


if __name__ == '__main__':
    main()
