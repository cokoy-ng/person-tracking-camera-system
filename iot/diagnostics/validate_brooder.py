"""Validación acotada del nuevo criadero. No referencia ni mueve la puerta."""
import argparse
import re
import json
import time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host"))
from serial_bridge import serial


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--actuate', action='store_true')
    args = parser.parse_args()
    results = {'port': args.port, 'physical_confirmation': False, 'commands': []}
    with serial.Serial(args.port, 115200, timeout=.2, write_timeout=2) as dev:
        def collect(seconds, expected=None):
            lines = []
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                line = dev.readline().decode('ascii', errors='replace').strip()
                if line:
                    print(line, flush=True); lines.append(line)
                    if line.startswith('ERR'):
                        raise RuntimeError(line)
                    if expected and line == expected:
                        return lines
            if expected:
                raise RuntimeError('Sin ACK: ' + expected)
            return lines
        def send(command, expected):
            dev.write((command+'\n').encode('ascii')); dev.flush()
            results['commands'].append(command)
            return collect(4, expected)
        def manual(index, mode, seconds=2):
            content = f'!{index}{mode}{seconds}'
            checksum = 0
            for b in content.encode('ascii'): checksum ^= b
            command = f'{content}*{checksum:02X}'
            send(command, 'OK CONTROL '+command)
        try:
            startup=collect(4)
            if not any(line in ('READY BROODER_12_PIN_REMAP','READY BROODER_13_MANUAL_DOOR','READY BROODER_14_PHYSICAL_CYCLES','READY BROODER_15_AUTO_CYCLES','READY BROODER_16_MANUAL_PUMP') for line in startup):
                raise RuntimeError('Firmware nuevo no identificado; no activar salidas')
            send('S', 'OK STOP')
            for index in range(5):
                if index!=3: manual(index, 1, 0)
            if not any(line in ('READY BROODER_14_PHYSICAL_CYCLES','READY BROODER_15_AUTO_CYCLES','READY BROODER_16_MANUAL_PUMP') for line in startup):
                send('4', 'OK CYCLE 4')
            samples=collect(9)
            results['sensor_lines']=[line for line in samples if line.startswith(('TEMP ', 'SENSOR ', 'CYCLE '))]
            results['sensor_ok']=any(line.startswith('TEMP ') for line in samples) and any(re.match(r'CYCLE id=[1-4] pin=[2-5] ',line) for line in samples)
            print('SENSOR_OK='+str(results['sensor_ok']), flush=True)
            if args.actuate:
                send('Z', 'OK SERVO TEST')
                results['servo_lines']=collect(26, 'OK SERVO DONE')
                results['servo_sequence_ack']=True
                # Alarm can be tested without temperature. Climate outputs retain protections.
                for index,name in [(4,'alarm'),(0,'heater'),(1,'pump'),(2,'fan')]:
                    if index!=4 and not results['sensor_ok']:
                        results[name]='skipped_sensor_fault'; continue
                    send('A', 'OK AUTO')
                    manual(index,2,2)
                    lines=collect(1)
                    states=[line for line in lines if line.startswith('CONTROL ')]
                    results[name]=states
                    manual(index,1,0)
                    send('S','OK STOP')
            print('RESULT '+json.dumps(results,ensure_ascii=False),flush=True)
        finally:
            send('S','OK STOP')
            manual(4,1,0)
            collect(.5)
    Path(__file__).with_name('brooder_validation_latest.json').write_text(json.dumps(results,indent=2),encoding='utf-8')

if __name__=='__main__': main()
