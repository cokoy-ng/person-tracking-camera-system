"""Cámara USB + modelos de emotion-detector/dev + servo D2 en COM3."""
import argparse
import importlib.util
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1] / 'ai' / 'comp_vision' / 'emotion-detector'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument('--name', default='USB 2.0 CAMERA')
    selector.add_argument('--index', type=int)
    parser.add_argument('--list', action='store_true', help='Listar cámaras sin cargar IA ni abrir Arduino')
    parser.add_argument('--port', default='COM3')
    parser.add_argument('--no-servo', action='store_true', help='Sin mover el servo; abre USB solo si se usa --light')
    parser.add_argument('--face-only', action='store_true', help='Solo rostros, sin personas ni expresiones')
    parser.add_argument('--no-humans', action='store_true', help='Desactivar detección de personas')
    parser.add_argument('--light', action=argparse.BooleanOptionalAction, default=True,
                        help='Luz D3 por presencia, activada por defecto (requiere firmware LIGHT_1)')
    parser.add_argument('--light-seconds', type=int, default=30, help='Segundos de luz tras la última detección (1..3600)')
    parser.add_argument('--sound-sensor', choices=('off', 'change', 'low', 'high'), default='change',
                        help='D4: una palmada enciende, tres apagan; change toma el reposo inicial, off desactiva sonido')
    parser.add_argument('--reverse', action='store_true', help='Invertir el sentido del servo')
    parser.add_argument('--min-angle', type=int, default=0)
    parser.add_argument('--max-angle', type=int, default=90)
    parser.add_argument('--seconds', type=float, default=0, help='0: hasta cerrar la ventana')
    parser.add_argument('--headless', action='store_true', help='Sin ventana, requiere --seconds')
    parser.add_argument('--check-models', action='store_true', help='Validar modelos sin abrir cámara ni servo')
    parser.add_argument('--stop-file', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.light_seconds <= 3600:
        parser.error('--light-seconds debe estar entre 1 y 3600')
    if not 0 <= args.min_angle < args.max_angle <= 180:
        parser.error('Se requiere 0 <= min-angle < max-angle <= 180')
    if args.seconds < 0 or (args.headless and args.seconds <= 0 and not args.check_models):
        parser.error('--headless requiere --seconds mayor que cero')
    if args.index is not None and args.index < 0:
        parser.error('--index debe ser >= 0')

    if sys.platform == 'linux' and 'microsoft' in platform.release().lower():
        from windows_ai import python_path
        python = python_path()
        if not python.exists():
            raise RuntimeError('Falta el entorno de IA. Consulta iot/README.md.')
        script = subprocess.check_output(['wslpath', '-w', str(Path(__file__).resolve())], text=True).strip()
        with tempfile.TemporaryDirectory(prefix='camera-tracking-') as folder:
            stop_file = Path(folder) / 'stop'
            win_stop = subprocess.check_output(['wslpath', '-w', str(stop_file)], text=True).strip()
            child = subprocess.Popen([str(python), '-u', script, *sys.argv[1:], '--stop-file', win_stop])
            try:
                return child.wait()
            except KeyboardInterrupt:
                print('\nDeteniendo cámara y servo…', flush=True)
                stop_file.touch()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.terminate()
                    child.wait(timeout=5)
                return 130

    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    def stopped():
        return args.stop_file is not None and args.stop_file.exists()

    import cv2
    from cv2_enumerate_cameras import enumerate_cameras
    from camera import select_camera
    backend = cv2.CAP_DSHOW if sys.platform == 'win32' else cv2.CAP_V4L2
    camera = None
    if args.list or not args.check_models:
        cameras = list(enumerate_cameras(backend))
        if args.list:
            for item in cameras:
                print(f'{item.index}: {item.name}', flush=True)
            if not cameras:
                print('No se detectaron cámaras.', flush=True)
            return 0
        camera = select_camera(cameras, args.name, args.index)
    from tracking_control import FaceServo, PresenceLight, select_target
    from human_detector import HumanDetector
    sys.path.insert(0, str(REPOSITORY))
    from detector import Detector

    print('Cargando modelos de emotion-detector/dev…', flush=True)
    detector = Detector(emotions=not args.face_only)
    humans = None if args.no_humans or args.face_only else HumanDetector()
    if humans:
        import numpy as np
        humans.detect(np.zeros((300, 300, 3), dtype=np.uint8))
        print('OK: detector de personas MobileNet-SSD cargado.', flush=True)
    print('OK: detector de rostros' + (' y modelo de expresiones cargados.' if not args.face_only else ' cargado.'), flush=True)
    if args.check_models or stopped():
        return 0
    capture = cv2.VideoCapture(camera.index, camera.backend)
    usb = None
    controller = FaceServo(args.min_angle, args.max_angle, args.reverse)
    presence_light = PresenceLight()
    title = 'Rostros, personas y servo - Q/Esc: salir - Espacio: pausar servo'
    frames = face_frames = person_frames = commands = 0
    paused = False
    expression, last_prediction = '', float('-inf')
    light_state, last_light_check = '', float('-inf')
    last_presence = False
    try:
        if not capture.isOpened():
            raise RuntimeError('No se pudo abrir la cámara USB. Cierra otras vistas de cámara.')
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        print(f'Cámara: {camera.name}, índice {camera.index}', flush=True)
        if not args.no_servo or args.light:
            spec = importlib.util.spec_from_file_location('arduino_usb', ROOT.parent / 'host' / 'serial_bridge.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            usb = module.USB(args.port)
            if not args.no_servo:
                print(f'Servo conectado: {usb.port}, D2, rango {args.min_angle}..{args.max_angle}', flush=True)
            if args.light:
                try:
                    usb.request('LIGHT PING')
                except RuntimeError as exc:
                    raise RuntimeError('El Arduino requiere el nuevo firmware LIGHT_1 para usar --light.') from exc
                usb.request(f'LIGHT HOLD {args.light_seconds}')
                usb.request(f'SOUND {args.sound_sensor.upper()}')
                print(f'Luz D3: presencia, {args.light_seconds} s; sonido D4: {args.sound_sensor}.', flush=True)
        if not args.headless:
            cv2.namedWindow(title, cv2.WINDOW_NORMAL)
        started = time.monotonic()
        while not stopped():
            if args.seconds and time.monotonic() - started >= args.seconds:
                break
            ok, frame = capture.read()
            if not ok or frame is None:
                raise RuntimeError('La cámara dejó de entregar imágenes.')
            frames += 1
            faces = detector.detect(frame)
            people = humans.detect(frame) if humans else []
            if people:
                person_frames += 1
            now = time.monotonic()
            if usb and args.light:
                present = bool(faces or people)
                light_command = presence_light.update(present, now)
                if light_command:
                    usb.request(light_command)
                if present != last_presence:
                    print('Luz: presencia detectada, renovando temporizador.' if present else
                          f'Luz: sin persona visible; {args.light_seconds} s de espera, renovables por sonido.', flush=True)
                    last_presence = present
                if now - last_light_check >= 1:
                    current_state = usb.request('LIGHT STATE')
                    if current_state != light_state:
                        print(f'D3: {current_state}', flush=True)
                    light_state, last_light_check = current_state, now
            selected, target_kind = select_target(faces, people)
            center = (selected[0] + selected[2]) / (2 * frame.shape[1]) if selected else None
            if faces:
                face_frames += 1
                if now - last_prediction >= 0.5:
                    expression = detector.emotion(frame, selected)
                    last_prediction = now
            else:
                expression = ''
            if usb and not args.no_servo and not paused:
                command = controller.update(center, now)
                if command:
                    print(f'{command} -> {usb.request(command)}', flush=True)
                    commands += 1
            if not args.headless:
                for box in people:
                    x1, y1, x2, y2 = box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 180, 0), 2)
                    cv2.putText(frame, 'Persona', (x1, max(15, y1 - 5)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 180, 0), 1)
                for box in faces:
                    x1, y1, x2, y2 = box
                    color = (0, 220, 0) if box == selected else (150, 150, 150)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                status = 'PAUSA' if paused else ('sin servo' if args.no_servo else f'Servo {controller.angle} grados')
                cv2.putText(frame, status, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
                cv2.putText(frame, f'{target_kind} {expression}',
                            (10, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                if args.light:
                    label = 'ON' if light_state == 'OK LIGHT ON' else 'OFF'
                    cv2.putText(frame, f'Luz D3: {label} | espera {args.light_seconds}s | sonido: {args.sound_sensor}',
                                (10, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                cv2.imshow(title, frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord('q')) or cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
                    break
                if key == ord(' ') and usb and not args.no_servo:
                    paused = not paused
                    usb.request('STOP')
                    controller.active, controller.streak = False, 0
        print(f'OK: {frames} fotogramas, {face_frames} con rostro, {person_frames} con persona, {commands} órdenes al servo.', flush=True)
    finally:
        try:
            if usb:
                usb.close()
                print('Servo liberado.', flush=True)
        finally:
            capture.release()
            if not args.headless:
                cv2.destroyAllWindows()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
