"""Snapshot local source and declared profiles without claiming device readback."""
import hashlib
import json
import re
from pathlib import Path
from brooder_stream import PROFILES


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def software_snapshot(root, port):
    root=Path(root)
    paths=sorted((root/'iot/firmware/brooder').glob('*.h'))+sorted((root/'iot/firmware/brooder').glob('*.ino'))
    paths += [root/'backend'/name for name in ('brooder_stream.py','main.py','event_history.py','configuration_audit.py')]
    paths += [root/'frontend/src/App.jsx']
    sources={str(path.relative_to(root)).replace('\\','/'):path.read_text(encoding='utf-8') for path in paths}
    banner=re.search(r'READY (BROODER_[A-Z0-9_]+)',sources.get('iot/firmware/brooder/brooder.ino',''))
    return {'schema_version':1, 'configuration_basis':'local_sources_and_backend_profiles_not_device_readback',
            'expected_firmware':banner[1] if banner else None,
            'port':port,'baudrate':115200,'profiles':PROFILES,'sources':sources}


def configuration_values(row):
    connected=bool(row.get('serial_connected'))
    cycle=row.get('cycle') or {}
    profile={key:value for key,value in cycle.items() if key not in ('humidifier','exhaust','intake','air_reason','valid')} if connected and cycle.get('valid') else {}
    controls=(row.get('controls') or {}) if connected and row.get('outputs_valid') else {}
    return {'profile':profile, 'modes':{key:value.get('mode') for key,value in controls.items()},
            'pins':row.get('pins') if connected else None,
            'door_enabled':row.get('door_enabled') if connected else None,
            'firmware_reported':row.get('firmware_reported') if connected else None}
