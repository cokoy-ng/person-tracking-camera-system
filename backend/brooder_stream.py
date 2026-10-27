"""Decodifica telemetría del criadero sin enviar órdenes al Arduino."""
import re
import time

TEMP = re.compile(r'TEMP (-?\d+) HUM (\d+)')
STATE = re.compile(r'STATE heater=([01]) alarm=([01]) position=(\d+) target=(\d+) referenced=([01]) stopped=([01])')
TRAVEL = 49152


class Telemetry:
    def __init__(self):
        self.sample = None
        self.sample_at = None

    def feed(self, line, now=None):
        now = time.monotonic() if now is None else now
        match = TEMP.fullmatch(line)
        if match:
            temperature, humidity = map(int, match.groups())
            if 0 <= temperature <= 50 and 0 <= humidity <= 100:
                self.sample = {'temperature': temperature, 'humidity': humidity}
                self.sample_at = now
            else:
                self.sample = None
            return None
        if line.startswith(('FAULT', 'READY')):
            self.sample = None
            return None
        match = STATE.fullmatch(line)
        if not match:
            return None
        heater, alarm, position, target, referenced, stopped = map(int, match.groups())
        if position > TRAVEL or target not in (0, TRAVEL):
            return None
        valid = self.sample is not None and now - self.sample_at < 6
        door = ('unknown' if not referenced else 'paused' if stopped else
                'sensor_fault' if not valid else
                'closing' if position < target else 'opening' if position > target else
                'closed' if position == TRAVEL else 'open')
        return {
            'ok': valid, 'serial_connected': True, 'outputs_valid': True,
            'timestamp': time.time(),
            'temperature': self.sample['temperature'] if valid else None,
            'humidity': self.sample['humidity'] if valid else None,
            'error': None if valid else 'Sin lectura válida reciente del DHT11 en A1',
            'heater': bool(heater), 'alarm': bool(alarm),
            'stopped': bool(stopped), 'referenced': bool(referenced),
            'position': position, 'target': target, 'door': door,
            'door_percent': round(position / TRAVEL * 100, 1) if referenced else None,
            'pins': {'temperature': 'A1', 'alarm': 'A0', 'heater': 'A2'},
        }
