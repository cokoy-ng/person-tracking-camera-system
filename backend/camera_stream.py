"""Relay the camera's in-memory stream without polling files or queuing video."""
from collections import deque
import json
import threading
import time
import urllib.request
import uuid

SOURCE = 'http://127.0.0.1:8766'
_streams = {}
_lock = threading.Lock()


def camera_status():
    try:
        with urllib.request.urlopen(SOURCE + '/status', timeout=2) as response:
            data = json.load(response)
        if data.get('ok') and data.get('transport') == 'memory-v1' and 0 <= time.time() - data['timestamp'] <= 3:
            result = {key: data[key] for key in ('ok', 'timestamp', 'name', 'width', 'height', 'frames', 'fps', 'device_fps', 'encode_ms')}
            with _lock:
                active = [value for value in _streams.values() if time.monotonic()-value['updated'] <= 3]
                result['stream_fps'] = round(max((value['fps'] for value in active), default=0), 1)
                result['frame_age_ms'] = round(max((value['age_ms'] for value in active), default=0), 1) if active else None
                result['viewers'] = len(active)
            return result
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return {'ok': False, 'error': 'Cámara sin imágenes recientes. Revisa la conexión USB y vuelve a ejecutar el lanzador.'}


def mjpeg_frames():
    """Runs in Starlette's thread pool; sensor polling stays on its own task."""
    stream_id = uuid.uuid4().hex
    times = deque(maxlen=90)
    try:
        with urllib.request.urlopen(SOURCE + '/stream', timeout=3) as response:
            while True:
                line = response.readline(256)
                if not line:
                    return
                if line != b'--frame\r\n':
                    continue
                headers = {}
                for _ in range(10):
                    line = response.readline(256)
                    if line == b'\r\n':
                        break
                    if not line:
                        return
                    name, value = line.decode('ascii').split(':', 1)
                    headers[name.lower()] = value.strip()
                else:
                    return
                length = int(headers['content-length'])
                if not 0 < length <= 4*1024*1024:
                    return
                jpeg = response.read(length)
                if len(jpeg) != length or not jpeg.startswith(b'\xff\xd8') or not jpeg.endswith(b'\xff\xd9'):
                    return
                # Discard old frames instead of replaying a backlog after a stall.
                age = time.time() - float(headers['x-captured-at'])
                if age > 0.5:
                    continue
                now = time.monotonic()
                times.append(now)
                span = times[-1]-times[0]
                with _lock:
                    _streams[stream_id] = dict(updated=now, fps=(len(times)-1)/span if span else 0,
                                              age_ms=max(0, age*1000))
                yield (b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ' +
                       str(length).encode() + b'\r\nX-Sequence: ' + headers['x-sequence'].encode() +
                       b'\r\nX-Captured-At: ' + headers['x-captured-at'].encode() + b'\r\n\r\n' + jpeg + b'\r\n')
    except (OSError, ValueError, KeyError):
        return
    finally:
        with _lock:
            _streams.pop(stream_id, None)
