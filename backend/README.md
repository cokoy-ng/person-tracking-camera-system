# Dashboard del criadero

Desde la raíz: `bash start.sh --dashboard --port COM3`.
Abrir **http://localhost:5173** en Windows. Backend: http://localhost:8000.
El firmware debe ser `iot/firmware/brooder`; el dashboard ya no envía `TEMP READ`.

El backend escucha las líneas `TEMP … HUM …` y `STATE …` de BROODER_3.
Abre COM sin activar DTR/RTS y no escribe comandos: abrir o cerrar el dashboard
no ordena movimientos ni apaga el controlador. El puerto permanece ocupado;
cerrar el dashboard antes de ejecutar otros scripts serie o cargar firmware.

Muestra temperatura/humedad de A1 (DHT11 digital), estado lógico de la alarma
A0, salida de calefacción A2, modo automático/pausa y posición estimada de
la puerta. A0 y A2 no son sensores analógicos: son salidas digitales.
La posición por pasos no confirma movimiento físico; alarma activa tampoco
confirma sonido. Datos viejos/desconectados se muestran como desconocidos.

- `GET /api/brooder` o `/api/temperature`: última telemetría.
- `GET /api/temperature/history`: últimas 120 muestras en memoria.
- `WS /ws/temperature`: cada muestra nueva, consumida por el frontend.

El backend corre con Python Windows por el acceso a COM. El frontend corre
con Vite en WSL. `VITE_API_BASE` puede configurar otro origen HTTP del backend.

Pruebas: `python3 -m unittest discover -s backend -p 'test_*.py' -v`.
Frontend: `cd frontend && npm run build && npm run lint`.
