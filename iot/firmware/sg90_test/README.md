# Prueba independiente del SG90: giro continuo

El usuario observó una vuelta completa y ausencia de retorno al mandar90.
Se trabaja con la hipótesis de giro continuo, pendiente de identificar el
modelo exacto. No considerar las órdenes anteriores como ángulos medidos.
En este modo los pulsos indican sentido/velocidad y1500us es el neutro
nominal; hay que calibrarlo si el eje deriva durante la espera.

## Conexión confirmada por el usuario

Anaranjado D2, rojo5V, marrónGND. Arduino Uno COM3 con actuadores del
criadero desconectados. La placa ejecuta esta prueba en lugar del criadero;
no escribe EEPROM. D2 no debe compartirse con el DHT11.
Si se usa fuente externa regulada de5V, unir las masas con Arduino.

## Giros rápidos individuales

`bash servo.sh derecha 45` hace un solo giro aproximado, sin retorno.
`bash servo.sh izquierda 45` necesita calibrar antes ese sentido.
Derecha: usuario observó unos90 grados con200ms; factor guardado2.222ms/grado.
La primera prueba45 usó100ms; medición visual pendiente.
Para explorar: `bash servo.sh izquierda 45 --ms 100` (ángulo desconocido).
Para registrar lo observado, por ejemplo30 grados:
`bash servo.sh izquierda 30 --calibrar` (guarda, no mueve).
El firmware acepta `TURN R 100` / `TURN L 100`, con duración20..5000ms;
termina en neutro300ms y detach. `STOP` cancela sin retorno.

## Ciclo único

Firmware `SG90_CONTINUOUS_3`: `CYCLE 200` ejecuta:

1. Pulso1600us durante200ms: primer sentido.
2. Neutro1500us durante3000ms.
3. Pulso1200us durante200ms: sentido inverso.
4. Neutro1500us durante300ms y desconexión de pulsos.

La duración por sentido admite50..500ms. Todo el ciclo lo temporiza Arduino,
incluso si se cierra el programa del PC. `STOP` cancela en cualquier fase
sin reanudar. Arranca sin pulsos. `SET` ya no se acepta para evitar confundir
velocidad con posición. No se modifica automáticamente la duración.

```powershell
./iot/host/upload_sg90.ps1 -Port COM3
# Usar Python con pyserial; Python312 base no lo tiene:
& "$env:LOCALAPPDATA/camera-ai/venv/Scripts/python.exe" ./iot/diagnostics/check_sg90.py --port COM3 --cycle --pulse-ms 200
```

Sin `--cycle` solo identifica el firmware. Antes de mover, el programa da
3segundos de aviso. Muestra FORWARD, WAIT, REVERSE, NEUTRAL y DONE.
Las respuestas confirman ejecución del programa, no posición física.

Igual tiempo en ambos sentidos no garantiza volver al mismo punto, por
carga, velocidad, holgura e inercia. Para una puerta con cierre reproducible
se necesita realimentación (por ejemplo finales de carrera) o un servo
posicional apropiado. No integrar todavía como control de puerta fiable.

Referencia sobre diferencia entre servo posicional y continuo:
https://github.com/microsoft/pxt-common-packages/blob/master/libs/servo/docs/reference/servos/set-angle.md
