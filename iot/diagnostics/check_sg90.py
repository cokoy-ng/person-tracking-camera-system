"""Prueba de giro continuo SG90: avance, parada 3s y reversa por tiempo."""
import argparse
import time

import serial


def wait_for(port, expected, seconds=3):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        response = port.readline().decode('ascii', errors='replace').strip()
        if response:
            print(response, flush=True)
        if response == expected:
            return
        if response.startswith('ERR'):
            raise RuntimeError(response)
    raise RuntimeError(f'Sin confirmación: se esperaba {expected!r}')


def request(port, command, expected):
    port.write((command + '\n').encode('ascii'))
    port.flush()
    wait_for(port, expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--cycle', action='store_true', help='Ejecutar un solo ciclo')
    parser.add_argument('--pulse-ms', type=int, default=200,
                        help='Duración de cada sentido, 50..500 ms; no son grados')
    args = parser.parse_args()
    if not 50 <= args.pulse_ms <= 500:
        parser.error('--pulse-ms debe estar entre 50 y 500')
    with serial.Serial(args.port, 115200, timeout=0.2, write_timeout=2) as port:
        time.sleep(2)
        port.reset_input_buffer()
        request(port, 'PING', 'PONG SG90_CONTINUOUS_3')
        if not args.cycle:
            print('Firmware identificado; no se ordenó movimiento.', flush=True)
            return
        print('Prueba en 3s: avance breve, pausa3s y reversa breve.', flush=True)
        try:
            time.sleep(3)
            request(port, f'CYCLE {args.pulse_ms}', 'OK CYCLE')
            wait_for(port, 'OK DONE', seconds=7)
        finally:
            request(port, 'STOP', 'OK STOP')
        print('Ciclo terminado; retorno físico aproximado pendiente de observar.', flush=True)


if __name__ == '__main__':
    main()
