# Arranque del monitor del criadero

Desde Ubuntu/WSL, en cualquier directorio:

```bash
/home/tucu/yo/person-tracking-camera-system/sh/levantar_todo.sh
```

Inicia frontend en http://localhost:5173 y backend de Windows en el puerto 8000. Reutiliza servicios existentes. Detecta un único Arduino por USB; si hay varios o el adaptador no se identifica, indica el puerto:

```bash
./sh/levantar_todo.sh --port COM6
./sh/levantar_todo.sh --watch
```

Comprueba HTTP del frontend, API del backend, conexión serie, sensor/ciclo válido, estado de salidas válido, lecturas recientes y al menos cinco muestras nuevas durante 15 segundos continuos. También verifica el handshake WebSocket y una muestra real del canal del dashboard. Esta prueba describe el intervalo observado; `--watch` permite seguir supervisando cada cinco segundos. Devuelve error si no puede confirmar estabilidad en 45 segundos.

Los servicios permanecen activos al terminar el lanzador o la vigilancia. Los logs están en `.runtime/frontend.log` y `.runtime/backend.log` para procesos iniciados por este lanzador; los servicios reutilizados conservan sus logs originales. Un fallo de verificación deja los servicios disponibles para diagnóstico. El puerto 8000 ocupado por otra aplicación genera un error.

Requiere WSL, Node con las dependencias de `frontend` instaladas y Python de Windows con las dependencias del backend. Puede configurarse `ARDUINO_WINDOWS_PYTHON` con la ruta WSL del ejecutable de Python.

El lanzador solo consulta telemetría: no envía STOP, reanudación, movimientos ni referencias de puerta, ni carga firmware. La bomba sigue exclusivamente manual. Arduino conserva su control autónomo; iniciar/cerrar este monitor no equivale a apagar hardware. La confirmación de salidas por software no prueba su funcionamiento físico.

## Iniciar, consultar y detener

En una terminal Ubuntu/WSL, desde cualquier carpeta:

```bash
# Iniciar todos los servicios y verificar conexión
/home/tucu/yo/person-tracking-camera-system/sh/levantar_todo.sh

# Consultar frontend, backend, Arduino y última lectura sin iniciar nada
/home/tucu/yo/person-tracking-camera-system/sh/levantar_todo.sh --estado

# Cerrar frontend y backend de este proyecto
/home/tucu/yo/person-tracking-camera-system/sh/levantar_todo.sh --stop

# Ver instrucciones completas
/home/tucu/yo/person-tracking-camera-system/sh/levantar_todo.sh --ayuda
```

`--stop` verifica que los puertos de los servicios dejen de responder. Identifica los procesos del proyecto por directorio y comando; no termina otras aplicaciones solo porque ocupen el mismo puerto. Conserva datos y registros. La vigilancia iniciada por esta versión termina al detectar la orden de parada.

Cerrar los servidores **no detiene el control autónomo de Arduino**. Si necesitas detener también los actuadores, usa primero **Pausar y detener** en el dashboard y apaga la alarma si corresponde; espera confirmación antes de cerrar los servicios. STOP no persiste después de reiniciar la placa. El lanzador no envía órdenes de actuación.

El código auxiliar está en `scrips/monitor_servicios.py`. La carpeta `sh/` contiene solamente el ejecutable `.sh`; esta documentación está en `docs/MONITOREO.md`.
