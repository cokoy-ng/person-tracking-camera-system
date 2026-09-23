"""Vista y captura de la cámara USB; ejecutable desde WSL o Windows."""
import argparse
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def positive(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Debe ser mayor que cero")
    return number


def select_camera(cameras, name, index):
    matches = [c for c in cameras if c.index == index] if index is not None else [
        c for c in cameras if c.name.casefold() == name.casefold()
    ]
    if len(matches) != 1:
        requested = f'índice {index}' if index is not None else repr(name)
        available = ', '.join(f'{c.index}: {c.name}' for c in cameras) or 'ninguna'
        reason = 'No se detecta la cámara' if not matches else 'Hay varias cámaras que coinciden con'
        raise RuntimeError(
            f'{reason} {requested}. Disponibles: {available}. '
            'Reconecta la cámara USB o elige una disponible con --name o --index. '
            'Usa --list para consultar las cámaras.')
    return matches[0]


def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Cámara USB: vista en vivo por defecto.")
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--name", default="USB 2.0 CAMERA", help="Nombre exacto; por defecto USB 2.0 CAMERA")
    selector.add_argument("--index", type=int, help="Índice mostrado por --list")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true", help="Listar cámaras sin capturar")
    mode.add_argument("--check", action="store_true", help="Leer 30 fotogramas sin abrir ventana")
    mode.add_argument("--snapshot", type=Path, help="Guardar una foto JPG o PNG y salir")
    parser.add_argument("--width", type=positive, default=640)
    parser.add_argument("--height", type=positive, default=480)
    parser.add_argument("--seconds", type=positive, help="Duración máxima de la vista en vivo")
    args = parser.parse_args()
    if args.index is not None and args.index < 0:
        parser.error("--index debe ser >= 0")
    if args.snapshot and args.snapshot.suffix.lower() not in (".jpg", ".jpeg", ".png"):
        parser.error("--snapshot debe terminar en .jpg o .png")

    if sys.platform == "linux" and "microsoft" in platform.release().lower():
        python = ROOT / ".venv-win" / "Scripts" / "python.exe"
        if not python.exists():
            raise RuntimeError("Falta .venv-win. Ejecuta python3 setup.py desde iot/tracking.")
        def windows_path(path):
            return subprocess.check_output(["wslpath", "-w", str(path.resolve())], text=True).strip()
        # Rebuild arguments so a Linux snapshot path becomes a valid Windows path.
        forwarded = ["--index", str(args.index)] if args.index is not None else ["--name", args.name]
        forwarded += ["--width", str(args.width), "--height", str(args.height)]
        if args.list:
            forwarded += ["--list"]
        elif args.check:
            forwarded += ["--check"]
        elif args.snapshot:
            forwarded += ["--snapshot", windows_path(args.snapshot)]
        if args.seconds:
            forwarded += ["--seconds", str(args.seconds)]
        child = subprocess.Popen([str(python), "-u", windows_path(Path(__file__)), *forwarded])
        try:
            return child.wait()
        except KeyboardInterrupt:
            # Windows does not always receive WSL's Ctrl+C. Do not leave the USB open.
            child.terminate()
            child.wait(timeout=5)
            return 130

    try:
        import cv2
        from cv2_enumerate_cameras import enumerate_cameras
    except ImportError as exc:
        raise RuntimeError("Faltan dependencias. Ejecuta python3 setup.py desde iot/tracking.") from exc
    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_V4L2
    cameras = list(enumerate_cameras(backend))
    if args.list:
        for camera in cameras:
            print(f"{camera.index}: {camera.name}", flush=True)
        if not cameras:
            raise RuntimeError("No se detectaron cámaras.")
        return 0
    camera = select_camera(cameras, args.name, args.index)
    capture = cv2.VideoCapture(camera.index, camera.backend)
    preview = not (args.check or args.snapshot)
    window = "Camara USB - Q o Esc para cerrar; S para guardar foto"
    frames = 0
    try:
        if not capture.isOpened():
            raise RuntimeError("No se pudo abrir la cámara. Cierra otras aplicaciones que la estén usando.")
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        print(f"Conectada: {camera.name} (índice {camera.index})", flush=True)
        if preview:
            cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        started = time.monotonic()
        while True:
            ok, frame = capture.read()
            if not ok or frame is None:
                raise RuntimeError("La cámara dejó de entregar imágenes. Revisa su conexión USB.")
            frames += 1
            if frames == 1:
                print(f"Imagen recibida: {frame.shape[1]} x {frame.shape[0]}", flush=True)
            if args.check and frames >= 30:
                break
            if args.snapshot and frames >= 10:
                save_frame(cv2, frame, args.snapshot)
                break
            if preview:
                cv2.imshow(window, frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")) or cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                    break
                if key == ord("s"):
                    save_frame(cv2, frame, ROOT / "captures" / f"camera_{time.time_ns()}.jpg")
                if args.seconds and time.monotonic() - started >= args.seconds:
                    break
        print(f"OK: {frames} fotogramas recibidos.", flush=True)
    finally:
        capture.release()
        if preview:
            cv2.destroyAllWindows()
    return 0


def save_frame(cv2, frame, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix, frame)
    if not ok:
        raise RuntimeError("No se pudo codificar la foto.")
    # Path handles UNC and Unicode filenames, including the WSL workspace.
    path.write_bytes(encoded.tobytes())
    print(f"Foto guardada: {path}", flush=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nCámara detenida.")
        sys.exit(130)
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
