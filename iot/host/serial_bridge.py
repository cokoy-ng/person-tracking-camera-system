"""Control USB del servo D2 desde Python en WSL o Windows."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
IOT_ROOT = ROOT.parent
# pySerial is pure Python: the Windows helper can use the WSL venv installation.
if sys.platform == "win32":
    for folder in (IOT_ROOT / ".venv" / "lib").glob("python*/site-packages"):
        sys.path.insert(0, str(folder))

import serial
from serial.tools import list_ports


class USB:
    def __init__(self, port=None):
        if not port:
            candidates = [p.device for p in list_ports.comports()
                          if p.vid in (0x2341, 0x2A03)]
            if len(candidates) != 1:
                raise RuntimeError("No hay un único Arduino detectado. Indica --port COM3 o /dev/ttyACM0.")
            port = candidates[0]
        self.port = port
        self.serial = serial.Serial(port, 115200, timeout=0.3, write_timeout=2)
        try:
            time.sleep(2)  # The Uno resets when its serial port opens.
            self.serial.reset_input_buffer()
            self.request("PING")
        except BaseException:
            self.serial.close()
            raise

    def request(self, command):
        self.serial.write((command + "\n").encode("ascii"))
        deadline = time.monotonic() + 3
        expected = {"PING": "PONG SERVO_USB_1", "STOP": "OK STOP"}.get(command)
        if command == "LIGHT PING":
            expected = "OK LIGHT_1"
        elif command == "LIGHT PERSON" or command.startswith("LIGHT HOLD ") or command in ("SOUND OFF", "SOUND LOW", "SOUND HIGH", "SOUND CHANGE"):
            expected = "OK " + command
        if command.startswith("SET "):
            expected = "OK " + command[4:]
        while time.monotonic() < deadline:
            response = self.serial.readline().decode("ascii", errors="replace").strip()
            if command == 'SOUND STATS':
                parts = response.split()
                if len(parts) == 4 and parts[:2] == ['OK', 'SOUND'] and all(p.isdigit() for p in parts[2:]):
                    return response
            if command == 'SOUND READ' and response in ('OK SOUND LOW', 'OK SOUND HIGH'):
                return response
            if command == 'TEMP READ':
                if response == 'ERR TEMP':
                    return response
                parts = response.split()
                if len(parts) == 4 and parts[:2] == ['OK', 'TEMP'] and all(p.lstrip('-').isdigit() for p in parts[2:]):
                    return response
            if command == 'LIGHT STATE' and response in ('OK LIGHT ON', 'OK LIGHT OFF'):
                return response
            if response == expected:
                return response
            if response.startswith("ERR"):
                raise RuntimeError(response)
        raise RuntimeError("Sin confirmación del Arduino. Carga firmware/servo_usb primero.")

    def close(self):
        try:
            self.request("STOP")
        finally:
            self.serial.close()


def worker(port):
    usb = USB(port)
    try:
        print("CONNECTED " + usb.port, flush=True)
        for line in sys.stdin:
            print(usb.request(line.strip()), flush=True)
    finally:
        usb.close()


class WindowsBridge:
    def __init__(self, port):
        windows_python = os.environ.get("ARDUINO_WINDOWS_PYTHON")
        if not windows_python:
            candidates = list(Path("/mnt/c/Users").glob("*/AppData/Local/Programs/Python/Python*/python.exe"))
            if len(candidates) != 1:
                raise RuntimeError("Indica ARDUINO_WINDOWS_PYTHON con la ruta /mnt/c/.../python.exe.")
            windows_python = str(candidates[0])
        script = subprocess.check_output(["wslpath", "-w", str(ROOT / "serial_bridge.py")], text=True).strip()
        args = [windows_python, "-u", script, "--worker"]
        if port:
            args += ["--port", port]
        self.process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        text=True, bufsize=1)
        response = self.process.stdout.readline().strip()
        if not response.startswith("CONNECTED "):
            self.close()
            raise RuntimeError("El puente USB de Windows no inició. Revisa el error anterior.")
        self.port = response.removeprefix("CONNECTED ") + " (puente Windows desde WSL)"

    def request(self, command):
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()
        response = self.process.stdout.readline().strip()
        if not response.startswith(("OK ", "PONG ")):
            raise RuntimeError("Fallo del puente USB: " + (response or "conexión cerrada"))
        return response

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=3)
        self.process.stdout.close()


def main():
    parser = argparse.ArgumentParser(description="Servo D2: órdenes por USB, sin Arduino IDE.")
    parser.add_argument("--port", help="COM3 (puente Windows) o /dev/ttyACM0 (Linux)")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--angle", type=int, choices=range(181), metavar="0..180")
    mode.add_argument("--demo", action="store_true", help="Alternar 0 y 90 cada segundo")
    mode.add_argument("--check", action="store_true", help="Comprobar respuesta del firmware sin mover")
    parser.add_argument("--cycles", type=int, default=0, help="Ciclos de demo; 0 = hasta Ctrl+C")
    args = parser.parse_args()
    if args.cycles < 0:
        parser.error("--cycles debe ser >= 0")
    if args.worker:
        worker(args.port)
        return
    if not (args.demo or args.check or args.angle is not None):
        parser.error("Usa --demo, --angle 90 o --check")
    wsl = sys.platform == "linux" and "microsoft" in os.uname().release.lower()
    bridge = wsl and (args.port or "COM").upper().startswith("COM")
    usb = WindowsBridge(args.port) if bridge else USB(args.port)
    try:
        print("Conectado: " + usb.port, flush=True)
        if args.check:
            print(usb.request("PING"), flush=True)
        elif args.angle is not None:
            print(usb.request(f"SET {args.angle}"), flush=True)
            time.sleep(1)
        else:
            print("Demo 0 ↔ 90. Ctrl+C para detener y liberar el servo.", flush=True)
            cycle = 0
            while args.cycles == 0 or cycle < args.cycles:
                for angle in (0, 90):
                    print(usb.request(f"SET {angle}"), flush=True)
                    time.sleep(1)
                cycle += 1
    except KeyboardInterrupt:
        print("\nDeteniendo…", flush=True)
    finally:
        usb.close()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
