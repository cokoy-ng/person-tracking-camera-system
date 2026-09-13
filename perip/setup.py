"""Instala el entorno de cámara en Windows y el de control en WSL."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    if sys.platform != "linux":
        raise RuntimeError("Ejecuta este instalador desde WSL con python3 setup.py.")
    configured = os.environ.get("ARDUINO_WINDOWS_PYTHON")
    candidates = [Path(configured)] if configured else list(
        Path("/mnt/c/Users").glob("*/AppData/Local/Programs/Python/Python*/python.exe"))
    if len(candidates) != 1:
        raise RuntimeError("Indica ARDUINO_WINDOWS_PYTHON con la ruta /mnt/c/.../python.exe.")
    def win(path):
        return subprocess.check_output(["wslpath", "-w", str(path)], text=True).strip()
    windows_env = ROOT / ".venv-win"
    if not (windows_env / "Scripts" / "python.exe").exists():
        subprocess.run([str(candidates[0]), "-m", "venv", win(windows_env)], check=True)
    executable = windows_env / "Scripts" / "python.exe"
    executable.chmod(executable.stat().st_mode | 0o111)
    subprocess.run([str(windows_env / "Scripts" / "python.exe"), "-m", "pip", "install",
                    "-r", win(ROOT / "requirements-windows.txt")], check=True)
    linux_env = ROOT / ".venv"
    if shutil.which("uv"):
        subprocess.run(["uv", "venv", "--allow-existing", "--python", "3.12", str(linux_env)], check=True)
        subprocess.run(["uv", "pip", "install", "--python", str(linux_env / "bin" / "python"),
                        "pyserial==3.5"], check=True)
    else:
        subprocess.run([sys.executable, "-m", "venv", str(linux_env)], check=True)
        subprocess.run([str(linux_env / "bin" / "python"), "-m", "pip", "install", "pyserial==3.5"], check=True)
    print("Listo. Ejecuta: source .venv/bin/activate")
    print("Cámara: python camera.py | Servo: python servo.py --check")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
