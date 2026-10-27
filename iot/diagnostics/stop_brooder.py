"""Pausa motor/calefacción del criadero. La alarma sigue supervisando.
El STOP es volátil: al reiniciar la placa vuelve al modo automático.
"""
import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
from serial_bridge import serial


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    args = parser.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    port = serial.Serial(port=None, baudrate=115200, timeout=0.5, write_timeout=2)
    port.dtr = False
    port.rts = False
    port.port = args.port
    with port:
        time.sleep(2.5)
        port.reset_input_buffer()
        for attempt in range(3):
            port.write(b'~S53\n')
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                line = port.readline().decode('ascii', errors='replace').strip()
                if line:
                    print(line, flush=True)
                if line.startswith('STATE ') and 'stopped=1' in line and 'heater=0' in line:
                    print('CONFIRMED STOPPED: motor/calefaccion en pausa; alarma sigue supervisando.', flush=True)
                    return
                if line == 'ERR FRAME':
                    break
        raise RuntimeError('No se confirmó STOP; no asumir que la placa esté detenida.')


if __name__ == '__main__':
    main()
