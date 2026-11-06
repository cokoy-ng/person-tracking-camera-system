#!/usr/bin/env bash
# =============================================================================
# Monitoreo de pollitos — sensores, dashboard, cámara y detección visual.
#
# Uso desde WSL (puedes ejecutarlo desde cualquier directorio):
#   ./sh/monitoreo_pollitos.sh               Inicia y verifica todos los servicios.
#   ./sh/monitoreo_pollitos.sh --estado      Muestra sensores, cámara y visión.
#   ./sh/monitoreo_pollitos.sh --stop        Cierra frontend, backend, cámara y visión.
#   ./sh/monitoreo_pollitos.sh --watch       Inicia y mantiene vigilancia de lecturas.
#   ./sh/monitoreo_pollitos.sh --port COM6   Usa ese puerto al iniciar un backend nuevo.
#   ./sh/monitoreo_pollitos.sh --ayuda       Muestra estas instrucciones.
#
# URL: http://localhost:5173/       API: http://localhost:8000/api/brooder
# Logs: .runtime/frontend.log, backend.log, camara.log y vision.log
# Ctrl+C en --watch termina la vigilancia; los servicios siguen activos.
# --stop cierra SERVICIOS, no corta alimentación ni envía STOP al Arduino.
# Para detener actuadores: usa primero «Pausar y detener» en el dashboard
# y apaga la alarma si corresponde. STOP es volátil al reiniciar la placa.
# No se carga firmware, no se mueve puerta/servo ni se cambia la bomba manual.
# Auxiliar Python: scrips/monitor_servicios.py. Detalles: docs/MONITOREO.md.
# =============================================================================
set -Eeuo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
mode=levantar
helper_args=()
while (($#)); do
    case "$1" in
        -h|--help|--ayuda) sed -n '3,21{s/^# \{0,1\}//;p;}' "${BASH_SOURCE[0]}"; exit 0 ;;
        --estado|--stop)
            [[ "$mode" == levantar ]] || { echo 'Elige solo un modo.' >&2; exit 1; }
            mode="${1#--}"; shift ;;
        --watch) helper_args+=(--watch); shift ;;
        --port)
            [[ $# -ge 2 && "$2" =~ ^[Cc][Oo][Mm][0-9]+$ ]] || { echo 'Uso: --port COM6' >&2; exit 1; }
            helper_args+=(--port "$2"); shift 2 ;;
        *) echo "Opción desconocida: $1. Usa --ayuda." >&2; exit 1 ;;
    esac
done
[[ "$mode" == levantar || ${#helper_args[@]} == 0 ]] || { echo '--estado/--stop no admiten --watch/--port.' >&2; exit 1; }
for required in curl wslpath; do command -v "$required" >/dev/null || { echo "Falta $required." >&2; exit 1; }; done
runtime_dir="$project_dir/.runtime"
mkdir -p "$runtime_dir"
python_win="${ARDUINO_WINDOWS_PYTHON:-/mnt/c/Users/User/AppData/Local/Programs/Python/Python312/python.exe}"
[[ -x "$python_win" ]] || { echo 'Configura ARDUINO_WINDOWS_PYTHON con el Python de Windows.' >&2; exit 1; }
export PYTHONIOENCODING=utf-8
helper_win="$(wslpath -w "$project_dir/scrips/monitor_servicios.py")"
camera_win="$(wslpath -w "$project_dir/scrips/camara.py")"
vision_win="$(wslpath -w "$project_dir/scrips/vision_pollitos.py")"
if [[ "$mode" == estado ]]; then
    echo '=== Estado del monitor ==='
    failed=0
    if curl --silent --fail --max-time 3 http://localhost:5173/ >/dev/null; then echo 'Frontend: ARRIBA — http://localhost:5173/'; else echo 'Frontend: CAÍDO'; failed=1; fi
    "$python_win" -X utf8 "$helper_win" --estado || failed=1
    "$python_win" -X utf8 "$camera_win" --estado || failed=1
    "$python_win" -X utf8 "$vision_win" --estado || failed=1
    exit "$failed"
fi
if [[ "$mode" == stop ]]; then
    echo '=== Deteniendo servicios del monitor ==='
    : > "$runtime_dir/monitor.stop"
    failed=0
    # Solo procesos Vite cuyo directorio pertenece a este frontend.
    for process_dir in /proc/[0-9]*; do
        [[ "$(readlink "$process_dir/cwd" 2>/dev/null || true)" == "$project_dir/frontend" ]] || continue
        command_line="$(tr '\0' ' ' < "$process_dir/cmdline" 2>/dev/null || true)"
        [[ "$command_line" == *vite* ]] || continue
        process_id="${process_dir##*/}"
        kill -TERM "$process_id" 2>/dev/null || failed=1
    done
    "$python_win" -X utf8 "$vision_win" --stop || failed=1
    "$python_win" -X utf8 "$helper_win" --stop || failed=1
    "$python_win" -X utf8 "$camera_win" --stop || failed=1
    for ((attempt=0; attempt<10; attempt++)); do
        if ! curl --silent --fail --max-time 1 http://localhost:5173/ >/dev/null; then break; fi
        sleep 1
    done
    if curl --silent --fail --max-time 1 http://localhost:5173/ >/dev/null; then
        echo 'Frontend aún responde; no se terminó un proceso ajeno al proyecto.' >&2; failed=1
    else echo 'Frontend: DETENIDO'; fi
    echo 'Datos e historial conservados. Arduino puede seguir funcionando de forma autónoma.'
    echo 'Esta orden no corta alimentación ni envía STOP a los actuadores.'
    exit "$failed"
fi
command -v flock >/dev/null || { echo 'Falta flock.' >&2; exit 1; }
command -v setsid >/dev/null || { echo 'Falta setsid.' >&2; exit 1; }
exec 9>"$runtime_dir/monitor.lock"
flock -n 9 || { echo 'Ya hay una verificación/vigilancia activa. Usa --estado o Ctrl+C en la vigilancia.' >&2; exit 1; }
echo '=== Monitoreo de pollitos recién nacidos ==='
echo "Proyecto: $project_dir"
echo '[1/5] Verificando dependencias…'
[[ -x "$project_dir/frontend/node_modules/.bin/vite" ]] || { echo 'Faltan dependencias: ejecuta npm install dentro de frontend.' >&2; exit 1; }
echo '[2/5] Frontend en puerto 5173…'
if ! curl --silent --fail --max-time 3 http://localhost:5173/ >/dev/null; then
    (exec 9>&-; setsid --fork bash -c 'cd "$1"; exec node_modules/.bin/vite --host 0.0.0.0 --port 5173 --strictPort' _ "$project_dir/frontend" >"$runtime_dir/frontend.log" 2>&1 < /dev/null)
else echo 'Frontend existente: se reutiliza.'; fi
frontend_ready=0
for ((attempt=0; attempt<20; attempt++)); do
    if curl --silent --fail --max-time 2 http://localhost:5173/ >/dev/null; then frontend_ready=1; break; fi
    sleep 1
done
[[ "$frontend_ready" == 1 ]] || { echo "Frontend no disponible. Revisa $runtime_dir/frontend.log" >&2; exit 1; }
echo '[3/5] Webcam USB: video para el dashboard…'
camera_failed=0
"$python_win" -X utf8 "$camera_win" || camera_failed=1
echo '[4/5] Detección de pollitos sobre la captura existente…'
vision_failed=0
"$python_win" -X utf8 "$vision_win" || vision_failed=1
echo '[5/5] Backend, Arduino, lecturas recientes y WebSocket…'
echo 'Comandos disponibles:'
echo "  Ver estado:  $project_dir/sh/monitoreo_pollitos.sh --estado"
echo "  Parar:       $project_dir/sh/monitoreo_pollitos.sh --stop"
echo "  Vigilar:     $project_dir/sh/monitoreo_pollitos.sh --watch"
echo "  Ayuda:       $project_dir/sh/monitoreo_pollitos.sh --ayuda"
echo "  Logs:        tail -f $runtime_dir/frontend.log $runtime_dir/backend.log $runtime_dir/camara.log $runtime_dir/vision.log"
echo 'Ctrl+C en vigilancia deja servicios activos. --stop no apaga Arduino.'
"$python_win" -X utf8 "$helper_win" "${helper_args[@]}"
exit "$((camera_failed || vision_failed))"
