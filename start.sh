#!/usr/bin/env bash
# Arranque desde Ubuntu WSL; admite ejecución desde cualquier directorio.
set -Eeuo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
tracking_dir="$project_dir/iot/tracking"
backend_dir="$project_dir/backend"
frontend_dir="$project_dir/frontend"

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }
trap 'printf "Error en el arranque (línea %s). Revisa el mensaje anterior.\n" "$LINENO" >&2' ERR

for argument in "$@"; do
    if [[ "$argument" == --help || "$argument" == -h ]]; then
        cat <<'HELP'
Uso: ./start.sh [--check | --setup-only | --dashboard] [opciones de tracking.py]

Sin opciones: prepara el entorno e inicia cámara, IA y servo.
--check       Verifica dependencias y carga modelos, sin abrir dispositivos.
--setup-only  Prepara y verifica dependencias, sin cargar modelos ni dispositivos.
--list        Lista las cámaras de Windows, sin cargar IA ni abrir Arduino.
--dashboard   Levanta el monitor web de temperatura/humedad (backend + frontend)
              en vez de cámara/servo. Usa el DHT11 en D5, no la cámara.

Ejemplos:
  ./start.sh
  ./start.sh --no-servo --seconds 10
  ./start.sh --face-only --reverse
  ./start.sh --port COM4 --name 'USB 2.0 CAMERA'
  ./start.sh --port COM3 --light --light-seconds 30
  ./start.sh --dashboard
  ./start.sh --dashboard --port COM6

--light requiere firmware actualizado y relé D3 configurado (ver LIGHT_CONTROL.md).

--dashboard y el modo normal NO pueden correr a la vez: ambos necesitan el
mismo puerto COM del Arduino en exclusiva. El lock de start.sh ya lo impide.

Lee .env junto al script si existe (ver .env.example).
Q/Esc cierra la ventana; Espacio pausa el servo; Ctrl+C detiene la aplicación
(o el dashboard, en modo --dashboard).
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
expect_port_value=0
tracking_args=()
for argument in "$@"; do
    if [[ "$expect_port_value" == 1 ]]; then
        export ARDUINO_PORT="$argument"
        expect_port_value=0
        tracking_args+=("$argument")
        continue
    fi
    case "$argument" in
        --check|--setup-only|--dashboard)
            [[ "$mode" == run ]] || fail 'Elige solo uno: --check, --setup-only o --dashboard.'
            mode="${argument#--}"
            ;;
        --name|--name=*|--index|--index=*)
            has_selector=1
            tracking_args+=("$argument")
            ;;
        --port)
            expect_port_value=1
            tracking_args+=("$argument")
            ;;
        --port=*)
            export ARDUINO_PORT="${argument#--port=}"
            tracking_args+=("$argument")
            ;;
        *) tracking_args+=("$argument") ;;
    esac
done

if [[ "$mode" == dashboard ]]; then
    for required_command in node npm; do
        command -v "$required_command" >/dev/null || fail "Falta el comando $required_command en WSL (necesario para el frontend)."
    done
    for relative_file in backend/main.py backend/run.ps1 iot/host/serial_bridge.py \
        frontend/package.json frontend/src/App.jsx; do
        [[ -s "$project_dir/$relative_file" ]] || fail "Falta $relative_file."
    done
else
    for relative_file in \
        ai/comp_vision/human-detector/deploy.prototxt ai/comp_vision/human-detector/mobilenet_iter_73000.caffemodel \
        iot/tracking/human_detector.py \
        iot/tracking/tracking.py iot/tracking/check_requirements.py iot/host/serial_bridge.py \
        ai/comp_vision/emotion-detector/detector.py ai/comp_vision/emotion-detector/requirements-windows.txt \
        ai/comp_vision/emotion-detector/model/67emotion_human.json ai/comp_vision/emotion-detector/model/67emotion_human.h5 \
        ai/comp_vision/emotion-detector/face_detector/deploy.prototxt \
        ai/comp_vision/emotion-detector/face_detector/res10_300x300_ssd_iter_140000.caffemodel; do
        [[ -s "$project_dir/$relative_file" ]] || fail "Falta $relative_file. Comprueba el proyecto y ai/comp_vision/emotion-detector."
    done
fi

# Evita dos arranques simultáneos con este lanzador, incluyendo instalaciones.
exec 9>"$tracking_dir/.tracking.lock"
flock -n 9 || fail 'Ya hay otra ejecución de start.sh. Ciérrala antes de iniciar otra.'

if [[ "$mode" == dashboard ]]; then
    printf '[1/2] Comprobando Python de Windows…\n'
else
    printf '[1/4] Comprobando Python de Windows…\n'
fi
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

if [[ "$mode" == dashboard ]]; then
    printf '[2/2] Levantando backend y frontend del dashboard…\n'
    if [[ ! -d "$frontend_dir/node_modules" ]]; then
        printf 'Instalando dependencias del frontend (primera vez)…\n'
        (cd -- "$frontend_dir" && npm install)
    fi
    # Job control propio: cada & queda en su grupo de procesos, para poder
    # matar el árbol completo de npm (que no siempre reenvía señales a sus
    # hijos) y para que la señal llegue de inmediato en vez de esperar a que
    # termine un comando en primer plano (así es como bash difiere las trampas).
    set -m
    powershell_exe="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    backend_script_win="$(wslpath -w "$backend_dir/run.ps1")"
    arduino_python_win="$(wslpath -w "$ARDUINO_WINDOWS_PYTHON")"
    "$powershell_exe" -NoProfile -ExecutionPolicy Bypass \
        -File "$backend_script_win" -Port "$ARDUINO_PORT" -Python "$arduino_python_win" &
    backend_job=$!
    # vite directo, sin pasar por "npm run dev": npm no siempre reenvía
    # señales a sus hijos y deja procesos sueltos al cerrar.
    (cd -- "$frontend_dir" && exec node_modules/.bin/vite --host) &
    frontend_job=$!
    cleanup_dashboard() {
        kill -- "-$frontend_job" 2>/dev/null || true
        kill -- "-$backend_job" 2>/dev/null || true
        # El proceso real de uvicorn corre en Windows; matar el PID de WSL
        # del puente de PowerShell no siempre lo termina del otro lado.
        "$powershell_exe" -NoProfile -Command \
            'Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*uvicorn*" -and $_.CommandLine -like "*backend*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }' \
            >/dev/null 2>&1 || true
    }
    trap cleanup_dashboard EXIT INT TERM
    printf 'Backend: http://localhost:8000 (Arduino en %s) | Frontend: http://localhost:5173\n' "$ARDUINO_PORT"
    printf 'Abre http://localhost:5173 en un navegador de Windows. Ctrl+C detiene ambos.\n'
    printf 'Si el backend de Windows queda colgado, ciérralo desde el Administrador de tareas.\n'
    wait -n "$backend_job" "$frontend_job" 2>/dev/null || true
    cleanup_dashboard
    exit 0
fi

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
requirements_path="$(wslpath -w "$project_dir/ai/comp_vision/emotion-detector/requirements-windows.txt")"
checker_path="$(wslpath -w "$tracking_dir/check_requirements.py")"
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
if [[ ! -x "$tracking_dir/.venv/bin/python" ]]; then
    python3 -m venv --without-pip "$tracking_dir/.venv"
fi
source "$tracking_dir/.venv/bin/activate"
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
exec "$tracking_dir/.venv/bin/python" "$tracking_dir/tracking.py" "${defaults[@]}" "${tracking_args[@]}"
