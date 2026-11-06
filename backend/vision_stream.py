"""Estado visual para React, independiente del lector serie y del video."""
import json
import math
from pathlib import Path
import sys
import time
import urllib.request
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'ai/comp_vision/chick-monitor'))
from behavior.configuration import validate as validate_configuration, DEFAULT

URL = 'http://127.0.0.1:8767/status'
MAX_AGE = 1.5


def normalize(data):
    status = data.get('status', 'unavailable')
    result = {key: data.get(key) for key in ('timestamp', 'captured_at', 'sequence', 'width', 'height',
        'fps', 'inference_ms', 'model', 'threshold', 'experimental')}
    result.update(status=status, fresh=False, detections=[], count=None, groups=[], near_pairs=[],
                  nearest_neighbors=[], zone_counts=[], confirmed_count=None)
    try:
        result['configuration'] = validate_configuration(data.get('configuration', DEFAULT))
    except (ValueError, TypeError):
        result['configuration'] = None
    stamp = data.get('captured_at')
    if status != 'ready' or not data.get('fresh'):
        return result
    if not isinstance(stamp, (int, float)) or not math.isfinite(stamp) or not 0 <= time.time()-stamp <= MAX_AGE:
        result['status'] = 'stale'
        return result
    boxes = data.get('detections')
    if not isinstance(boxes, list) or len(boxes) > 100:
        result['status'] = 'error'
        return result
    valid = []
    for box in boxes:
        if not isinstance(box, dict):
            continue
        values = [box.get(key) for key in ('x', 'y', 'width', 'height', 'confidence')]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= 1 for v in values):
            continue
        x, y, width, height, confidence = values
        if width <= 0 or height <= 0 or x+width > 1.001 or y+height > 1.001 or confidence < 0.4:
            continue
        normalized = dict(x=x, y=y, width=width, height=height, confidence=confidence, label='Pollito')
        track_id = box.get('track_id')
        if isinstance(track_id, int) and not isinstance(track_id, bool) and 0 < track_id <= 10**9:
            normalized.update(track_id=track_id, confirmed=box.get('confirmed') is True, trail=[])
            trail = box.get('trail', [])
            if isinstance(trail, list):
                for point in trail[-24:]:
                    if isinstance(point, dict) and all(isinstance(point.get(k), (int, float)) and math.isfinite(point[k]) for k in ('x', 'y', 'timestamp')) and 0 <= point['x'] <= 1 and 0 <= point['y'] <= 1 and 0 <= stamp-point['timestamp'] <= 6.1:
                        normalized['trail'].append({key: point[key] for key in ('x', 'y', 'timestamp')})
        valid.append(normalized)
    if len(valid) != len(boxes):
        result['status'] = 'error'
        return result
    result.update(status='ready', fresh=True, detections=valid, count=len(valid))
    observed = {box['track_id']: box for box in valid if box.get('confirmed')}
    result['confirmed_count'] = len(observed)
    session = data.get('tracking_session')
    result['tracking_session'] = session if isinstance(session, str) and len(session) <= 32 else None
    configuration = result['configuration']
    if configuration and data.get('configuration_revision') == configuration['revision']:
        groups = data.get('groups', [])
        for group in (groups[:50] if isinstance(groups, list) else []):
            if not isinstance(group, dict):
                continue
            ids = group.get('ids')
            duration = group.get('duration_seconds')
            if not isinstance(ids, list) or not all(isinstance(i, int) and i in observed for i in ids) or len(set(ids)) < configuration['min_group_size']:
                continue
            if not isinstance(duration, (int, float)) or not math.isfinite(duration) or not 0 <= duration <= 10**8 or not isinstance(group.get('id'), int):
                continue
            boxes = [observed[i] for i in set(ids)]
            x, y = min(b['x'] for b in boxes), min(b['y'] for b in boxes)
            right, bottom = max(b['x']+b['width'] for b in boxes), max(b['y']+b['height'] for b in boxes)
            result['groups'].append(dict(id=group['id'], ids=sorted(set(ids)), count=len(set(ids)), duration_seconds=duration,
                persistent=duration >= configuration['persistence_seconds'], x=x,y=y,width=right-x,height=bottom-y))
        for zone in configuration['zones']:
            ids = [key for key, box in observed.items() if zone['x'] <= box['x']+box['width']/2 < zone['x']+zone['width'] and zone['y'] <= box['y']+box['height']/2 < zone['y']+zone['height']]
            result['zone_counts'].append(dict(id=zone['id'], count=len(ids), ids=sorted(ids)))
    for key, a, b, limit in (('near_pairs', 'a', 'b', 200), ('nearest_neighbors', 'track_id', 'neighbor_id', 100)):
        items = data.get(key, [])
        if not isinstance(items, list):
            continue
        for pair in items[:limit]:
            if not isinstance(pair, dict):
                continue
            first, second, separation = pair.get(a), pair.get(b), pair.get('distance_ratio')
            if isinstance(first, int) and isinstance(second, int) and first in observed and second in observed and first != second and isinstance(separation, (int, float)) and math.isfinite(separation) and 0 <= separation <= 1:
                if key != 'near_pairs' or (configuration and data.get('configuration_revision') == configuration['revision'] and separation <= configuration['near_ratio']):
                    result[key].append({a:first, b:second, 'distance_ratio':separation})
    return result


def vision_status():
    try:
        with urllib.request.urlopen(URL, timeout=1) as response:
            data = json.load(response)
        return normalize(data)
    except (OSError, ValueError, TypeError, AttributeError):
        return dict(status='unavailable', fresh=False, detections=[], count=None, groups=[], near_pairs=[], nearest_neighbors=[], zone_counts=[])


def configuration_request(payload=None):
    request = 'http://127.0.0.1:8767/config'
    if payload is not None:
        payload = validate_configuration(payload)
        request = urllib.request.Request(request, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=3) as response:
        return validate_configuration(json.load(response))
