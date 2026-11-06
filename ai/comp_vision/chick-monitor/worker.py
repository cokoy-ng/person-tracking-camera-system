"""Inferencia aislada: consume la captura existente; nunca abre USB ni puerto COM."""
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time
import urllib.request
from behavior.configuration import Configuration, Conflict

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]
ADDRESS = ('127.0.0.1', 8767)
SOURCE = 'http://127.0.0.1:8766'
MAX_RESULT_AGE = 1.5


class Vision:
    def __init__(self, configuration_path=None):
        self.stopped = threading.Event()
        self.lock = threading.Lock()
        self.result = dict(status='loading', error=None, count=None, detections=[], timestamp=None)
        self.configuration = Configuration(configuration_path)

    def snapshot(self):
        with self.lock:
            result = dict(self.result)
        stamp = result.get('captured_at')
        result['fresh'] = (result['status'] == 'ready' and isinstance(stamp, (int, float)) and
                           0 <= time.time()-stamp <= MAX_RESULT_AGE and not self.stopped.is_set())
        if not result['fresh']:
            result['detections'] = []
            result['count'] = None
            result.update(groups=[], near_pairs=[], nearest_neighbors=[], zone_counts=[], confirmed_count=None)
        configuration = self.configuration.get()
        if result.get('configuration_revision') != configuration['revision']:
            result.update(groups=[], near_pairs=[], zone_counts=[])
        return dict(result, project=str(PROJECT), pid=os.getpid(), model='chicken-yolov8n',
                    threshold=0.4, experimental=True, version=2, configuration=configuration)

    def set_result(self, **result):
        with self.lock:
            self.result = result

    def run(self):
        try:
            import cv2
            import numpy as np
            from detector.yolo import ChickenDetector
            from tracking.temporary import TemporaryTracker
            from behavior.spatial import SpatialAnalysis
            detector = ChickenDetector()
            detector.detect(np.zeros((240, 320, 3), dtype=np.uint8))
        except Exception as exc:
            self.set_result(status='error', error=str(exc), count=None, detections=[], timestamp=time.time())
            print('ERROR cargando detector:', exc, flush=True)
            return
        sequence = 0
        times = deque(maxlen=30)
        tracker, spatial = TemporaryTracker(), SpatialAnalysis()
        while not self.stopped.is_set():
            try:
                # Sequential requests always obtain the newest frame, without a queue.
                with urllib.request.urlopen(SOURCE + f'/frame?after={sequence}', timeout=3) as response:
                    sequence = int(response.headers['X-Sequence'])
                    captured_at = float(response.headers['X-Captured-At'])
                    content = response.read(4*1024*1024)
                if time.time()-captured_at > 0.75:
                    continue
                image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
                if image is None:
                    raise ValueError('Fotograma inválido')
                started = time.perf_counter()
                detections = detector.detect(image)
                detections = tracker.update(detections, captured_at, image.shape[1], image.shape[0])
                configuration = self.configuration.get()
                analysis = spatial.update(detections, captured_at, image.shape[1], image.shape[0], configuration)
                elapsed = time.perf_counter()-started
                now = time.time()
                times.append(time.monotonic())
                span = times[-1]-times[0]
                self.set_result(status='ready', error=None, timestamp=now, captured_at=captured_at,
                    sequence=sequence, width=image.shape[1], height=image.shape[0],
                    count=len(detections), detections=detections, inference_ms=round(elapsed*1000, 1),
                    fps=round((len(times)-1)/span, 1) if span >= 1 else 0,
                    tracking_session=tracker.session, configuration_revision=configuration['revision'], **analysis)
            except Exception as exc:
                tracker.clear()
                spatial.clear()
                self.set_result(status='waiting_camera', error=str(exc), count=None, detections=[], timestamp=time.time())
                self.stopped.wait(0.5)


def main():
    os.environ.setdefault('YOLO_CONFIG_DIR', str(Path(os.environ['LOCALAPPDATA']) / 'chick-monitor' / 'settings'))
    os.environ.setdefault('YOLO_AUTOINSTALL', 'false')
    vision = Vision(PROJECT / 'backend/data/vision_config.json')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path not in ('/status', '/config'):
                self.send_error(404)
                return
            content = json.dumps(vision.configuration.get() if self.path == '/config' else vision.snapshot(), allow_nan=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            try:
                self.wfile.write(content)
            except OSError:
                pass

        def do_POST(self):
            self.connection.settimeout(3)
            if self.path == '/config':
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 8192:
                        raise ValueError('Configuración demasiado grande o vacía')
                    content = vision.configuration.save(json.loads(self.rfile.read(length)))
                    status = 200
                except Conflict as exc:
                    content, status = dict(detail=str(exc)), 409
                except (ValueError, TypeError) as exc:
                    content, status = dict(detail=str(exc)), 400
                except OSError:
                    content, status = dict(detail='No se pudo guardar la configuración visual'), 500
                body = json.dumps(content).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path != '/stop':
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Length', '0')
            self.end_headers()
            vision.stopped.set()

    server = ThreadingHTTPServer(ADDRESS, Handler)
    server.daemon_threads = True
    def shutdown():
        vision.stopped.wait()
        server.shutdown()
    threading.Thread(target=vision.run, daemon=True).start()
    threading.Thread(target=shutdown, daemon=True).start()
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        vision.stopped.set()
        server.server_close()


if __name__ == '__main__':
    main()
