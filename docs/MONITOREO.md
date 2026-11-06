# Monitoreo de pollitos recién nacidos

Desde Ubuntu/WSL, en cualquier directorio:

```bash
/home/tucu/yo/person-tracking-camera-system/sh/monitoreo_pollitos.sh
```

Inicia frontend en http://localhost:5173, backend de Windows en el puerto 8000 y captura de la webcam `USB 2.0 CAMERA`. Pulsa **Ver cámara** en el dashboard para ver el video en la misma página; **Ocultar cámara** cierra esa vista. La cámara no usa el puerto COM ni envía órdenes al Arduino. Reutiliza servicios existentes. Detecta un único Arduino por USB; si hay varios o el adaptador no se identifica, indica el puerto:

```bash
./sh/monitoreo_pollitos.sh --port COM6
./sh/monitoreo_pollitos.sh --watch
```

Comprueba HTTP del frontend, API del backend, conexión serie, sensor/ciclo válido, estado de salidas válido, lecturas recientes y al menos cinco muestras nuevas durante 15 segundos continuos. También verifica el handshake WebSocket y una muestra real del canal del dashboard. Esta prueba describe el intervalo observado; `--watch` permite seguir supervisando cada cinco segundos. Devuelve error si no puede confirmar estabilidad en 45 segundos.

Los servicios permanecen activos al terminar el lanzador o la vigilancia. Los logs están en `.runtime/frontend.log` y `.runtime/backend.log` para procesos iniciados por este lanzador; los servicios reutilizados conservan sus logs originales. Un fallo de verificación deja los servicios disponibles para diagnóstico. El puerto 8000 ocupado por otra aplicación genera un error.

Requiere WSL, Node con las dependencias de `frontend` instaladas y Python de Windows con las dependencias del backend. Puede configurarse `ARDUINO_WINDOWS_PYTHON` con la ruta WSL del ejecutable de Python.

El lanzador solo consulta telemetría: no envía STOP, reanudación, movimientos ni referencias de puerta, ni carga firmware. La bomba sigue exclusivamente manual. Arduino conserva su control autónomo; iniciar/cerrar este monitor no equivale a apagar hardware. La confirmación de salidas por software no prueba su funcionamiento físico.

## Iniciar, consultar y detener

En una terminal Ubuntu/WSL, desde cualquier carpeta:

```bash
# Iniciar todos los servicios y verificar conexión
/home/tucu/yo/person-tracking-camera-system/sh/monitoreo_pollitos.sh

# Consultar frontend, backend, Arduino, cámara y última lectura sin iniciar nada
/home/tucu/yo/person-tracking-camera-system/sh/monitoreo_pollitos.sh --estado

# Cerrar frontend, backend y cámara de este proyecto
/home/tucu/yo/person-tracking-camera-system/sh/monitoreo_pollitos.sh --stop

# Ver instrucciones completas
/home/tucu/yo/person-tracking-camera-system/sh/monitoreo_pollitos.sh --ayuda
```

`--stop` verifica que los puertos de los servicios dejen de responder. Identifica los procesos del proyecto por directorio y comando; no termina otras aplicaciones solo porque ocupen el mismo puerto. Conserva datos y registros. La vigilancia iniciada por esta versión termina al detectar la orden de parada.

Cerrar los servidores **no detiene el control autónomo de Arduino**. Si necesitas detener también los actuadores, usa primero **Pausar y detener** en el dashboard y apaga la alarma si corresponde; espera confirmación antes de cerrar los servicios. STOP no persiste después de reiniciar la placa. El lanzador no envía órdenes de actuación.

La webcam se gestiona con `scrips/camara.py`, usando el entorno existente `iot/tracking/.venv-win`, sin ventanas de escritorio. Su inicio verifica imágenes reales; `--estado` comprueba proceso y fotogramas recientes y `--watch` también informa su estado. `--stop` libera la webcam. Ocultar el video en el navegador corta la descarga, pero mantiene la captura disponible para otras pestañas. La vista de prueba anterior se reemplaza por la integrada para evitar ocupar dos veces la cámara. Logs en `.runtime/camara.log`. No se escriben fotogramas en disco, no se conserva un historial de video ni se analiza con IA. Si falta la cámara, los sensores se inician igualmente y el lanzador informa el fallo de video.

El backend entrega estado en `GET /api/camera` y video MJPEG en `GET /api/camera/stream`. `scrips/camera_capture.py` usa Media Foundation y conserva solo el último JPEG en memoria. Publica un servicio interno exclusivamente en Windows `127.0.0.1:8766`; el backend retransmite ese flujo desde un hilo, sin bloquear telemetría ni abrir otra webcam. No hay esperas artificiales entre fotogramas ni colas de imágenes; se descartan fotogramas que lleven más de 500 ms en transporte al backend. Un video caducado deja de transmitirse y la interfaz muestra el problema y reintenta automáticamente.

El panel muestra FPS medidos de captura y envío. La edad indicada mide desde la captura entregada por OpenCV hasta el backend; no incluye exposición del sensor ni presentación del navegador. El 6 de noviembre se midieron inicialmente 3,19 FPS recibidos con el transporte antiguo por archivos. La consulta nativa de Windows anunció solo dos modos para esta webcam: YUY2 320×240 a 4 y a 2 FPS. Media Foundation capturó aproximadamente 4,1 FPS; DirectShow aproximadamente 3,1 FPS, incluso sin transmisión web. Solicitar 30 FPS no habilita un modo que Windows no anuncia.

El código auxiliar está en `scrips/monitor_servicios.py` y `scrips/camara.py`. La carpeta `sh/` contiene solamente el ejecutable `.sh`; esta documentación está en `docs/MONITOREO.md`.

## Detección de pollitos

El lanzador también inicia el proceso de visión gestionado por `scrips/vision_pollitos.py`.
Código y modelos están exclusivamente en `ai/comp_vision/chick-monitor/`. Consume
la captura existente y mantiene independiente el video. No abre otro lector USB
ni accede al puerto serie. `--estado`, `--watch` y `--stop` incluyen visión.
Un fallo de visión no impide intentar iniciar/verificar los sensores.

En **Ver cámara** aparecen recuadros con confianza, cantidad estimada de posibles
pollitos y velocidad de análisis. Resultados caducados se eliminan y no se muestran
como cero. El conteo está en evaluación, con falsos positivos observados en objetos
del montaje; aún no está validado en recién nacidos. El análisis no gobierna salidas.

Preparación única con Python de Windows: `ai/comp_vision/chick-monitor/evaluation/setup_windows.py`.
Entorno aislado: `%LOCALAPPDATA%/chick-monitor/venv`. No se reinstala al arrancar.
Modelo con hash y revisión fijos. Log: `.runtime/vision.log`. API pública:
`GET /api/vision`; servicio interno de inferencia: Windows `127.0.0.1:8767`.
Detalles y evaluación en [chick-monitor](../ai/comp_vision/chick-monitor/README.md).

La visión incluye IDs temporales, trayectorias de hasta 6 s, vecinos cercanos y
grupos sostenidos. Valores iniciales: proximidad 12 % de la diagonal de imagen,
mínimo 3 IDs y 5 s continuos. Son criterios visuales configurables, no centímetros
ni diagnóstico de causas térmicas. Los IDs pueden cambiar en cruces u oclusiones.

Pulsa **Configurar zonas y cercanía**, elige **Dibujar** para comedero, bebedero o
calefacción y arrastra sobre el video; después **Guardar configuración**. Las zonas
empiezan sin configurar. Se guardan junto con los criterios en
`backend/data/vision_config.json` y se conservan al reiniciar. No borrar este archivo.
Una revisión antigua recibe409 para no sobrescribir otra pestaña. `Cancelar`
descarta el borrador y no escribe. API `GET/POST /api/vision/config`.
