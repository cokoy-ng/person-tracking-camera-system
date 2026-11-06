"""Capture once, keep only the newest JPEG in RAM and serve it over loopback."""
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading
import time
from urllib.parse import parse_qs, urlsplit

ADDRESS = ('127.0.0.1', 8766)


class Capture:
    def __init__(self):
        self.changed = threading.Condition()
        self.stopped = threading.Event()
        self.jpeg = None
        self.sequence = 0
        self.timestamp = 0
        self.times = deque(maxlen=90)
        self.details = {}
        self.error = 'Iniciando cámara'

    def publish(self, jpeg, details):
        now = time.time()
        with self.changed:
            self.jpeg = jpeg
            self.sequence += 1
            self.timestamp = now
            self.times.append(time.perf_counter())
            self.details = details
            self.changed.notify_all()

    def status(self):
        with self.changed:
            elapsed = self.times[-1] - self.times[0] if len(self.times) > 1 else 0
            return dict(self.details, ok=bool(self.jpeg) and not self.stopped.is_set() and
                        0 <= time.time() - self.timestamp <= 3,
                        mode='web', transport='memory-v1', frame_api=1, pid=os.getpid(), timestamp=self.timestamp,
                        frames=self.sequence, fps=round((len(self.times)-1)/elapsed, 1) if elapsed else 0,
                        error=self.error)

    def next_frame(self, previous):
        with self.changed:
            self.changed.wait_for(lambda: self.sequence != previous or self.stopped.is_set(), timeout=2)
            if self.stopped.is_set() or self.sequence == previous or time.time() - self.timestamp > 3:
                return None
            return self.sequence, self.timestamp, self.jpeg

    def stop(self):
        self.stopped.set()
        with self.changed:
            self.changed.notify_all()

    def run(self):
        import cv2
        from cv2_enumerate_cameras import enumerate_cameras
        from camera import select_camera
        camera = select_camera(list(enumerate_cameras(cv2.CAP_MSMF)), 'USB 2.0 CAMERA', None)
        device = cv2.VideoCapture(camera.index, camera.backend)
        try:
            if not device.isOpened():
                raise RuntimeError('No se pudo abrir la webcam USB')
            device.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            device.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            device.set(cv2.CAP_PROP_FPS, 30)
            device.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            device_fps = device.get(cv2.CAP_PROP_FPS)
            print(f'Captura en memoria: {camera.name}; Media Foundation; modo {device_fps} FPS.', flush=True)
            while not self.stopped.is_set():
                ok, frame = device.read()
                captured_at = time.time()
                if not ok or frame is None:
                    raise RuntimeError('La cámara dejó de entregar imágenes')
                ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if not ok:
                    raise RuntimeError('No se pudo codificar el video')
                self.publish(encoded.tobytes(), dict(name=camera.name, width=frame.shape[1],
                    height=frame.shape[0], device_fps=device_fps,
                    encode_ms=round((time.time()-captured_at)*1000, 1)))
                self.error = None
        except Exception as exc:
            self.error = str(exc)
            print('ERROR captura:', exc, flush=True)
        finally:
            device.release()
            self.stop()


def serve_capture():
    capture = Capture()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *args):
            pass

        def do_POST(self):
            if self.path != '/stop':
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Length', '0')
            self.end_headers()
            capture.stop()

        def do_GET(self):
            self.connection.settimeout(3)
            route = urlsplit(self.path)
            if route.path == '/frame':
                try:
                    previous = int(parse_qs(route.query).get('after', ['0'])[0])
                except ValueError:
                    self.send_error(400)
                    return
                frame = capture.next_frame(previous)
                if frame is None:
                    self.send_error(503)
                    return
                sequence, stamp, jpeg = frame
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(len(jpeg)))
                self.send_header('X-Sequence', str(sequence))
                self.send_header('X-Captured-At', str(stamp))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                try:
                    self.wfile.write(jpeg)
                except OSError:
                    pass
                return
            if self.path == '/status':
                content = json.dumps(capture.status()).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(content)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                try:
                    self.wfile.write(content)
                except OSError:
                    pass
                return
            if self.path != '/stream':
                self.send_error(404)
                return
            if not capture.status()['ok']:
                self.send_error(503)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'close')
            self.end_headers()
            sequence = 0
            try:
                while True:
                    frame = capture.next_frame(sequence)
                    if frame is None:
                        return
                    sequence, stamp, jpeg = frame
                    self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ' +
                        str(len(jpeg)).encode() + b'\r\nX-Sequence: ' + str(sequence).encode() +
                        b'\r\nX-Captured-At: ' + str(stamp).encode() + b'\r\n\r\n' + jpeg + b'\r\n')
                    self.wfile.flush()
            except (OSError, TimeoutError):
                pass
            finally:
                self.close_connection = True

    server = ThreadingHTTPServer(ADDRESS, Handler)
    server.daemon_threads = True
    def run():
        try:
            capture.run()
        except Exception as exc:
            print('ERROR cámara:', exc, flush=True)
            capture.stop()
    def shutdown():
        capture.stopped.wait()
        server.shutdown()
    threading.Thread(target=run, daemon=True).start()
    threading.Thread(target=shutdown, daemon=True).start()
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        capture.stop()
        server.server_close()
