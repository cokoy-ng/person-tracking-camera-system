#!/usr/bin/env bash
# Uso: bash servo.sh derecha 45 | bash servo.sh izquierda 20
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec /mnt/c/Users/User/AppData/Local/camera-ai/venv/Scripts/python.exe iot/diagnostics/girar_servo.py "$@"
