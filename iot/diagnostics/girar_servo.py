"""Giro único: derecha/izquierda y grados estimados mediante calibración."""
import argparse
import json
import math
from pathlib import Path
import time

import serial
from check_sg90 import request, wait_for

CONFIG = Path(__file__).with_name('sg90_calibracion.json')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('direccion', choices=['derecha', 'izquierda'])
    p.add_argument('grados', type=float)
    p.add_argument('--port', default='COM3')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--ms', type=int, help='Pulso exploratorio; no garantiza los grados pedidos')
    mode.add_argument('--calibrar', action='store_true', help='Guardar grados observados del último pulso, sin mover')
    a = p.parse_args()
    if not math.isfinite(a.grados) or not 0 < a.grados <= 360:
        p.error('Los grados deben estar entre 0 (excluido) y 360.')
    data = json.loads(CONFIG.read_text()) if CONFIG.exists() else {'ms_por_grado': {}, 'ultimo': None}
    if a.calibrar:
        last = data['ultimo']
        if not last or last['direccion'] != a.direccion or not last['completado']:
            p.error('No hay un pulso completado en ese sentido para calibrar.')
        data['ms_por_grado'][a.direccion] = last['ms'] / a.grados
        CONFIG.write_text(json.dumps(data, indent=2) + '\n')
        print(f'Calibración guardada: {a.direccion}, {a.grados:g} grados observados. Sin movimiento.')
        return
    rate = data['ms_por_grado'].get(a.direccion)
    if a.ms is None and rate is None:
        p.error('Falta calibrar este sentido. Usar --ms 200 para observar, luego --calibrar con los grados observados.')
    duration = a.ms if a.ms is not None else round(a.grados * rate)
    if not 20 <= duration <= 5000:
        p.error('La duración debe estar entre 20 y 5000 ms; reducir los grados solicitados.')
    note = 'exploratorio, ángulo desconocido' if a.ms is not None else f'{a.grados:g} grados estimados'
    print(f'{a.direccion}: {duration} ms ({note}). Un solo giro, sin retorno.', flush=True)
    with serial.Serial(a.port, 115200, timeout=0.2, write_timeout=2) as port:
        time.sleep(2)
        port.reset_input_buffer()
        request(port, 'PING', 'PONG SG90_CONTINUOUS_3')
        try:
            print('Movimiento en 3 segundos.', flush=True)
            time.sleep(3)
            data['ultimo'] = {'direccion': a.direccion, 'ms': duration, 'completado': False}
            CONFIG.write_text(json.dumps(data, indent=2) + '\n')
            direction = 'R' if a.direccion == 'derecha' else 'L'
            request(port, f'TURN {direction} {duration}', 'OK TURN')
            wait_for(port, 'OK DONE', seconds=duration / 1000 + 3)
            data['ultimo']['completado'] = True
            CONFIG.write_text(json.dumps(data, indent=2) + '\n')
        finally:
            request(port, 'STOP', 'OK STOP')


if __name__ == '__main__':
    main()
