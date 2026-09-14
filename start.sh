#!/usr/bin/env bash
# Arranque desde Ubuntu WSL; admite ejecución desde cualquier directorio.
set -Eeuo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
perip_dir="$project_dir/perip"

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }
trap 'printf "Error en el arranque (línea %s). Revisa el mensaje anterior.\n" "$LINENO" >&2' ERR

for argument in "$@"; do
    if [[ "$argument" == --help || "$argument" == -h ]]; then
        cat <<'HELP'
Uso: ./start.sh [--check | --setup-only] [opciones de tracking.py]

Sin opciones: prepara el entorno e inicia cámara, IA y servo.
--check       Verifica dependencias y carga modelos, sin abrir dispositivos.
--setup-only  Prepara y verifica dependencias, sin cargar modelos ni dispositivos.
--list        Lista las cámaras de Windows, sin cargar IA ni abrir Arduino.

Ejemplos:
  ./start.sh
  ./start.sh --no-servo --seconds 10
  ./start.sh --face-only --reverse
  ./start.sh --port COM4 --name 'USB 2.0 CAMERA'
  ./start.sh --port COM3 --light --light-seconds 30

--light requiere firmware actualizado y relé D3 configurado (ver LIGHT_CONTROL.md).

Lee .env junto al script si existe (ver .env.example).
Q/Esc cierra la ventana; Espacio pausa el servo; Ctrl+C detiene la aplicación.
HELP
        exit 0
    fi
done

[[ "$(uname -r)" == *[Mm]icrosoft* ]] || fail 'Ejecuta este script desde Ubuntu WSL.'
for required_command in python3 wslpath flock; do
    command -v "$required_command" >/dev/null || fail "Falta el comando $required_command en WSL."
done

if [[ -f "$project_dir/.env" ]]; then
    set -a
    # Configuración local en sintaxis de Bash.
    source "$project_dir/.env"
    set +a
fi
export CAMERA_NAME="${CAMERA_NAME:-USB 2.0 CAMERA}"
export ARDUINO_PORT="${ARDUINO_PORT:-COM3}"
export CAMERA_REVERSE="${CAMERA_REVERSE:-0}"
[[ "$CAMERA_REVERSE" == 0 || "$CAMERA_REVERSE" == 1 ]] || fail 'CAMERA_REVERSE debe ser 0 o 1.'

mode=run
has_selector=0
tracking_args=()
for argument in "$@"; do
    case "$argument" in
        --check|--setup-only)
            [[ "$mode" == run ]] || fail 'Elige solo uno: --check o --setup-only.'
            mode="${argument#--}"
            ;;
        --name|--name=*|--index|--index=*)
            has_selector=1
            tracking_args+=("$argument")
            ;;
        *) tracking_args+=("$argument") ;;
    esac
done

for relative_file in \
    human-detector/deploy.prototxt human-detector/mobilenet_iter_73000.caffemodel \
    perip/human_detector.py \
    perip/tracking.py perip/check_requirements.py arduino/servo.py \
    emotion-detector/detector.py emotion-detector/requirements-windows.txt \
    emotion-detector/model/67emotion_human.json emotion-detector/model/67emotion_human.h5 \
    emotion-detector/face_detector/deploy.prototxt \
    emotion-detector/face_detector/res10_300x300_ssd_iter_140000.caffemodel; do
    [[ -s "$project_dir/$relative_file" ]] || fail "Falta $relative_file. Comprueba el proyecto y emotion-detector/dev."
done

# Evita dos arranques simultáneos con este lanzador, incluyendo instalaciones.
exec 9>"$perip_dir/.tracking.lock"
flock -n 9 || fail 'Ya hay otra ejecución de start.sh. Ciérrala antes de iniciar otra.'

printf '[1/4] Comprobando Python de Windows…\n'
if [[ -z "${ARDUINO_WINDOWS_PYTHON:-}" ]]; then
    shopt -s nullglob
    base_candidates=(/mnt/c/Users/*/AppData/Local/Programs/Python/Python312/python.exe)
    shopt -u nullglob
    [[ ${#base_candidates[@]} == 1 ]] || fail 'Configura ARDUINO_WINDOWS_PYTHON en .env con la ruta /mnt/c/.../python.exe de Python 3.12.'
    export ARDUINO_WINDOWS_PYTHON="${base_candidates[0]}"
fi
[[ -x "$ARDUINO_WINDOWS_PYTHON" ]] || fail "No se puede ejecutar $ARDUINO_WINDOWS_PYTHON. Usa una ruta de WSL."
"$ARDUINO_WINDOWS_PYTHON" -c 'import sys; print("Python Windows:", sys.version.split()[0]); sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)' \
    || fail 'Se requiere Python 3.12 de Windows y la interoperabilidad de WSL habilitada.'

if [[ -z "${CAMERA_AI_PYTHON:-}" ]]; then
    windows_appdata="$("$ARDUINO_WINDOWS_PYTHON" -c 'import os; print(os.environ["LOCALAPPDATA"])')"
    windows_appdata="${windows_appdata%$'\r'}"
    local_appdata="$(wslpath -u "$windows_appdata")"
    export CAMERA_AI_PYTHON="$local_appdata/camera-ai/venv/Scripts/python.exe"
fi
[[ "$CAMERA_AI_PYTHON" == /mnt/*/Scripts/python.exe ]] \
    || fail 'CAMERA_AI_PYTHON debe apuntar a un entorno de Windows: /mnt/c/.../Scripts/python.exe.'

printf '[2/4] Preparando entorno de IA y dependencias…\n'
if [[ ! -f "$CAMERA_AI_PYTHON" ]]; then
    ai_env_dir="$(dirname -- "$(dirname -- "$CAMERA_AI_PYTHON")")"
    "$ARDUINO_WINDOWS_PYTHON" -m venv "$(wslpath -w "$ai_env_dir")"
fi
[[ -x "$CAMERA_AI_PYTHON" ]] || fail "No se puede ejecutar $CAMERA_AI_PYTHON."
requirements_path="$(wslpath -w "$project_dir/emotion-detector/requirements-windows.txt")"
checker_path="$(wslpath -w "$perip_dir/check_requirements.py")"
if "$CAMERA_AI_PYTHON" "$checker_path" "$requirements_path"; then
    :
else
    checker_status=$?
    [[ "$checker_status" == 1 ]] || fail 'No se pudo comprobar el entorno de IA. Corrige el error anterior antes de instalar.'
    printf 'Instalando las versiones requeridas en el entorno de IA…\n'
    "$CAMERA_AI_PYTHON" -m pip install --disable-pip-version-check -r "$requirements_path"
    "$CAMERA_AI_PYTHON" "$checker_path" "$requirements_path"
fi
"$CAMERA_AI_PYTHON" -m pip check

printf '[3/4] Preparando ejecución desde WSL…\n'
# El lanzador Linux solo usa la biblioteca estándar; la IA y pySerial corren en Windows.
if [[ ! -x "$perip_dir/.venv/bin/python" ]]; then
    python3 -m venv --without-pip "$perip_dir/.venv"
fi
source "$perip_dir/.venv/bin/activate"
printf 'Cámara: %s | Puerto predeterminado: %s\n' "$CAMERA_NAME" "$ARDUINO_PORT"
printf 'Python de IA: %s\n' "$CAMERA_AI_PYTHON"
if [[ "$mode" == setup-only ]]; then
    printf 'OK: entorno preparado. Ejecuta ./start.sh para iniciar.\n'
    exit 0
fi

defaults=(--port "$ARDUINO_PORT")
if [[ "$has_selector" == 0 ]]; then
    defaults+=(--name "$CAMERA_NAME")
fi
if [[ "$CAMERA_REVERSE" == 1 ]]; then
    defaults+=(--reverse)
fi
if [[ "$mode" == check ]]; then
    tracking_args+=(--check-models)
    printf '[4/4] Validando modelos sin abrir cámara ni servo…\n'
else
    printf '[4/4] Iniciando cámara, rostros, personas y control configurado del servo…\n'
fi
cd -- "$project_dir"
exec "$perip_dir/.venv/bin/python" "$perip_dir/tracking.py" "${defaults[@]}" "${tracking_args[@]}"
