# Control manual del criadero

BROODER_11_HEAT_LIMIT: puerta D8–D11 deshabilitada; conserva referencia EEPROM.
Salidas HIGH: calefacción A2, humedad D7, extracción A4, entrada A5, alarma A0.
A1/A3 libres. No se modifica el cableado analógico restante.

Cada salida tiene Automático, Apagar y Encender. La duración se elige entre
1 y 1440 minutos en el dashboard; 0 segundos en API significa mantener hasta
pulsar Automático. El valor inicial del formulario es 5 minutos.
Reiniciar la placa borra los modos manuales. En automático A4/A5 trabajan juntos;
en manual pueden probarse individualmente. La alarma lógica sigue supervisando
aunque su salida se silencie temporalmente.

STOP y fallo de sensor bloquean calefacción y ventiladores; temperatura máxima
bloquea calor, humedad máxima bloquea humidificación y temperatura mínima bloquea
extracción/entrada. Los mandos no cambian esas protecciones. El estado eléctrico
no confirma movimiento, calor o sonido físicos. La prueba de alarma es independiente.

POST /api/control acepta output (heater/humidifier/exhaust/intake/alarm), mode
(auto/off/on) y duration_seconds (0..86400). El único lector serie envía la orden
con checksum XOR y espera OK CONTROL y telemetría;
sin confirmación la API devuelve error. CONTROL informa los cinco modos y salidas,
y door_enabled y remaining por salida. Los controles caducan tras 6 s sin telemetría y la UI los deshabilita.

Calefacción automática: ON a maxTemp-1, OFF al llegar a maxTemp. En ciclo4:
26 °C / 27 °C; ciclo3: 28/29; ciclo2:31/32; ciclo1:33/34.
Espera de 60s para reencender después de apagarse; máximo/fallo cortan de inmediato.
La demanda térmica de ventilación usa esos mismos bordes para no cortar el calor
en el antiguo centro. Las pruebas manuales siguen pudiendo cambiar antes del minuto.

Los registros se guardan automáticamente en archivos del proyecto:
- `backend/data/events.csv`: cambios, mandos, alarmas y conexión.
- `backend/data/readings.csv`: cada telemetría recibida con columnas numéricas.

El índice transaccional SQLite permanece en
`LOCALAPPDATA/camera-brooder/events.sqlite3` (Windows), con los eventos anteriores.
No se usa SQLite directamente en la carpeta WSL compartida: su bloqueo desde
Windows impide iniciar el servidor. Los CSV del proyecto se escriben y sincronizan
a disco después de cada lote, aunque el navegador esté cerrado. Al reiniciar,
se regeneran por lotes y reemplazo atómico desde SQLite para recuperar cualquier
escritura incompleta. Si falla el CSV, el índice conserva los registros y el panel
muestra el error; la siguiente escritura intenta completar lo pendiente.
Conservar tanto el índice como los CSV al hacer una copia de seguridad. Para abrir
en Excel durante la ejecución, descargar una copia desde el dashboard.

La tabla `events` guarda cambios de temperatura/HR, salidas, modos, duración,
alertas y conexión. La tabla `readings` guarda cada telemetría recibida, incluso
con valores repetidos, con columnas numéricas y modos de salida.
La frecuencia sigue la telemetría recibida: no se deben interpretar filas como
nuevas mediciones independientes del DHT11. Las marcas de tiempo corresponden a
la recepción en el servidor. No se reconstruyen periodos sin conexión o servidor.
Cerrar el navegador no interrumpe el registro mientras el backend esté activo.

GET `/api/events?page=1&page_size=25&kind=all` pagina desde SQLite, máximo 100
registros por petición. Devuelve total, pages, page, page_size y snapshot_id.
Para recorrer sin duplicar/saltar eventos nuevos, enviar el mismo snapshot_id
al cambiar de página. La UI muestra 25 por página; «Ver más recientes» renueva
la vista. Filtros: all, reading, output, alarm, connection, sensor, cycle, system.

Descargas completas, ordenadas por id ascendente, por lotes de 500 filas:
- `/api/history/readings.csv`: todas las muestras recibidas.
- `/api/history/events.csv?kind=all`: todos los eventos (o categoría elegida).

CSV UTF-8 con BOM, coma separadora y punto decimal. `timestamp_utc` es ISO 8601
UTC y `timestamp_epoch` son segundos Unix; la tabla web usa hora local del navegador.
`temperature_c`, `humidity_pct`, `cycle`, límites y umbrales son numéricos.
`serial_connected`, `sensor_valid`, `outputs_valid`, `stopped`, `alarm_active`
y las columnas `*_on` usan 1/0 (pueden aparecer como 1.0/0.0); vacío indica desconocido, nunca apagado supuesto.
`*_mode`: auto/off/on; `*_remaining_seconds`: tiempo restante reportado;
0 con modo manual significa sin temporizador. `output`, `mode`, `output_on` y
`duration_seconds` describen el mando/evento, cuando están disponibles.
En eventos antiguos no se inventan los campos que no se guardaban.
`alarm_reasons` y `air_reason` conservan las máscaras numéricas del firmware.
El CSV de eventos respeta la categoría seleccionada, incluye todas sus páginas.
Los estados eléctricos no prueban movimiento físico, calor ni sonido.

## Auditoría de configuraciones y resultados

Desde esta versión, `readings.csv` y `events.csv` incluyen `config_id` y
`session_id`. Cada arranque del backend obtiene una sesión nueva. Los registros
anteriores conservan vacío lo que no se conocía entonces; nunca se les asigna la
configuración actual de forma retroactiva.

`backend/data/configurations.csv` conserva versiones identificadas por id y hash:
ciclo/perfil completo, rangos, umbrales, modos, pines reportados, puerta habilitada
y última solicitud manual confirmada del dashboard (incluye duración y request_id).
Cambiar duración manteniendo el mismo modo también crea una versión distinta.
Una cuenta regresiva o un cambio de salida automática no crea otra configuración.
La configuración puede reutilizarse si vuelve exactamente al mismo estado;
los eventos y sesiones permiten separar los periodos de uso.

`backend/data/software/<sha256>.json` conserva las reglas completas: fuentes de
firmware, backend y pantalla, cuatro perfiles declarados y puerto/baudrate.
Se toma una versión al iniciar el servidor; los cambios de fuentes se aplican y
registran en el siguiente reinicio. No se guardan secretos de .env.
`GET /api/configurations/{id}` descarga el detalle junto con sus fuentes originales.
El firmware esperado se obtiene de las fuentes; `firmware_reported` solo se completa
si se recibió READY. Ninguno de ellos prueba por sí solo que el binario cargado
coincida exactamente con los archivos locales. No reiniciar la placa para rellenarlo.

`GET /api/history/configurations.csv` descarga todas las versiones. En el historial
hay filtros Configuraciones, Mandos y resultados, y Reinicios y STOP.
La paginación sigue siendo de 25 filas. Los registros de órdenes incluyen
`request_id`, `command_status` (requested/confirmed/rejected/unconfirmed),
duración, motivo, código HTTP, configuración previa, `before_json` y `after_json`.
Una solicitud sin confirmación no significa que la salida no haya cambiado.
Los estados previos y posteriores corresponden a la telemetría observada.
La petición se guarda antes de enviarse; si no puede persistirse, no se envía.
Las peticiones inválidas se registran como rechazadas; no se guardan cuerpos
arbitrarios de solicitudes inválidas. Un reinicio durante un mando puede dejar
solo requested, sin resultado conocido. Los cambios externos sin confirmación
no se atribuyen a una persona ni a una causa inventada.

Columnas para analizar resultados:
- temperature_in_range / humidity_in_range: 1 dentro del rango, 0 fuera.
- temperature_error_to_center_c / humidity_error_to_center_pct: desviación con signo
  frente al centro de referencia. El centro térmico NO es el umbral de apagado:
  calefacción se mantiene en max-1 / max como solicitó el usuario.
- Objetivos, límites, umbrales de humedad/ventilación, espera del foco, alarma
  pendiente/recuperando/sonando, STOP y posición/referencia de puerta reportada.
- Estado eléctrico, modo y segundos restantes de cada salida.

Para comparar ajustes, unir config_id con configurations.id y separar sesiones,
ciclos y periodos manuales/automáticos. Comparar desviaciones, tiempo aproximado
fuera del rango y número de conmutaciones usando intervalos entre timestamps;
no sumar huecos de conexión ni contar muestras repetidas como nuevas mediciones
independientes. Los cambios de ambiente se observan; los datos por sí solos no
prueban causalidad ni mejoría en la salud de los pollitos. Cambios físicos como
cableado, nivel de agua o alimentación no se detectan automáticamente.
