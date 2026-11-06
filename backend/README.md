> Actualización 2026-11-04: dashboard con sensor D5, servo D6, bomba D7, ventilador D8, calefacción D9 y alarma A0. A1–A5 libres. Ver [mapa y protocolo actuales](../iot/firmware/brooder/PIN_REMAP_2026_11_04.md). `POST /api/device` controla ciclo, servo, pausa y reanudación; cada orden queda auditada. El servo no se reintenta sin ACK.

# Dashboard del criadero — cuatro ciclos

Arranque: `bash start.sh --dashboard --port COM3` desde la raíz.
Windows: http://localhost:5173; API http://localhost:8000.
Backend Python Windows, escucha serie a 115200 sin enviar órdenes ni activar DTR/RTS.
El puerto queda ocupado: cerrar dashboard antes de cargar firmware o usar diagnósticos.
Cerrar dashboard no detiene el controlador autónomo.

El firmware informa TEMP/HUM, CYCLE, ALERT y STATE cada 2,5 s.
El pin de señal del único DHT11 selecciona el ciclo (D2–D5); A1 ya no participa.
API REST /api/brooder y /api/temperature, historial /api/temperature/history,
WebSocket /ws/temperature. Las respuestas incluyen cycle (perfil, centros,
umbrales y tres salidas de aire), alert (pendiente/confirmada/recuperación/pulso) y estado.
Sin ciclo confirmado la temperatura no se presenta como válida para control.
Diagnósticos separados caducan a los 6 s. La interfaz descarta telemetría
vieja/desconectada; no muestra salidas antiguas como actuales.

El panel presenta los cuatro ciclos, objetivo central, calor A2, humidificación
interna D7, extracción A4, entrada A5, alarma A0 y puerta estimada D8–D11.
STATE alarm es la alerta lógica, no el nivel de A0:
señal sonora 1 s cada minuto tras 30 s fuera de rango (fallos 10 s).

Pruebas: `python3 -m unittest discover -s backend -p 'test_*.py' -v`.
Frontend: `npm run build` y `npm run lint`. Escenarios UI verifican los cuatro
pines, alarma pendiente/confirmada/recuperación, pérdida de sensor y caducidad.
