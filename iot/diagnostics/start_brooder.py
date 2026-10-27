"""Inicia una sesión con la puerta FÍSICAMENTE abierta y activa el automático.

No usar para consultar estado: reinicia la referencia de posición a abierto.
Ejecutar con Python Windows. El controlador continúa autónomo al salir.
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
        # Dejar estabilizar el enlace y descartar texto previo al comando.
        time.sleep(2.5)
        port.reset_input_buffer()
        def request(command, expected):
            frame = f'~{command}{ord(command):02X}\n'
            # Cada orden es idempotente. Reintentar la misma, nunca avanzar
            # a la referencia siguiente sin confirmación.
            for attempt in range(3):
                port.write(frame.encode('ascii'))
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    line = port.readline().decode('ascii', errors='replace').strip()
                    if line:
                        print(line, flush=True)
                    if line == expected:
                        return
                    if line == 'ERR FRAME':
                        break
                    if line.startswith('ERR'):
                        raise RuntimeError(line)
            raise RuntimeError('Sin confirmacion: ' + expected)

        request('S', 'OK STOP')
        request('O', 'OK REFERENCE OPEN')
        request('A', 'OK AUTO')
        deadline = time.monotonic() + 165
        last_report = 0
        while time.monotonic() < deadline:
            line = port.readline().decode('ascii', errors='replace').strip()
            if not line:
                continue
            if line.startswith('STATE '):
                if 'referenced=0' in line:
                    raise RuntimeError('Se perdio la referencia durante el recorrido.')
                if time.monotonic() - last_report >= 20:
                    print(line, flush=True)
                    last_report = time.monotonic()
                if 'position=49152 target=49152' in line:
                    print('CIERRE COMPLETADO POR CONTEO: ' + line, flush=True)
                    return
            elif line.startswith('TEMP '):
                temperature = float(line.split()[1])
                if temperature > 32:
                    print(line, flush=True)
                    print('Temperatura alta: puerta abierta, automatico activo.', flush=True)
                    return
            else:
                print(line, flush=True)
        raise RuntimeError('No se confirmo el cierre en el plazo; revisar sensor y estado.')


if __name__ == '__main__':
    main()
