import copy
import json
import math
from pathlib import Path
import threading

LABELS = {'feeder': 'Comedero', 'drinker': 'Bebedero', 'heater': 'Calefacción'}
DEFAULT = dict(revision=0, near_ratio=0.12, min_group_size=3, persistence_seconds=5, zones=[])


def number(value, low, high):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and low <= value <= high


def validate(data):
    if not isinstance(data, dict) or set(data)-set(DEFAULT):
        raise ValueError('Configuración visual inválida')
    if not number(data.get('revision'), 0, 10**9) or not isinstance(data['revision'], int):
        raise ValueError('Falta la revisión de la configuración')
    if not number(data.get('near_ratio'), 0.03, 0.4):
        raise ValueError('La cercanía debe estar entre 3 y 40 % de la diagonal')
    if not number(data.get('min_group_size'), 2, 20) or not isinstance(data['min_group_size'], int):
        raise ValueError('El tamaño mínimo debe ser un entero entre 2 y 20')
    if not number(data.get('persistence_seconds'), 2, 300):
        raise ValueError('La persistencia debe estar entre 2 y 300 segundos')
    zones = data.get('zones')
    if not isinstance(zones, list) or len(zones) > 3:
        raise ValueError('Se admiten comedero, bebedero y calefacción')
    seen = set()
    cleaned = []
    for zone in zones:
        if not isinstance(zone, dict) or set(zone) != {'id', 'x', 'y', 'width', 'height'}:
            raise ValueError('Zona inválida')
        key = zone['id']
        if not isinstance(key, str) or key not in LABELS or key in seen:
            raise ValueError('Zona desconocida o duplicada')
        seen.add(key)
        if not all(number(zone.get(k), 0, 1) for k in ('x', 'y', 'width', 'height')):
            raise ValueError('La zona debe quedar dentro de la imagen')
        if zone['width'] < 0.02 or zone['height'] < 0.02 or zone['x']+zone['width'] > 1.000001 or zone['y']+zone['height'] > 1.000001:
            raise ValueError('La zona es demasiado pequeña o sale de la imagen')
        cleaned.append(dict(zone))
    return dict(revision=data['revision'], near_ratio=float(data['near_ratio']),
                min_group_size=data['min_group_size'], persistence_seconds=float(data['persistence_seconds']), zones=cleaned)


class Conflict(ValueError):
    pass


class Configuration:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.lock = threading.Lock()
        self.data = copy.deepcopy(DEFAULT)
        self.error = None
        if self.path and self.path.exists():
            try:
                self.data = validate(json.loads(self.path.read_text(encoding='utf-8')))
            except (OSError, ValueError, TypeError) as exc:
                self.error = 'No se pudo leer la configuración guardada; revisa el archivo antes de guardar.'
                print('ERROR configuración visual:', exc, flush=True)

    def get(self):
        with self.lock:
            return copy.deepcopy(self.data)

    def save(self, payload):
        data = validate(payload)
        with self.lock:
            if self.error:
                raise ValueError(self.error)
            if data['revision'] != self.data['revision']:
                raise Conflict('La configuración cambió en otra sesión. Recarga las zonas antes de guardar.')
            data['revision'] += 1
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_suffix('.tmp')
                temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
                temporary.replace(self.path)
            self.data = data
            return copy.deepcopy(data)
