# Luz por presencia o sonido

Actualización del sonido: **una palmada enciende; tres seguidas apagan**.
Deja entre 0.18 y 0.9 segundos entre palmadas (aproximadamente medio segundo).
Tras más de 0.9 segundos sin una nueva palmada comienza una secuencia nueva.
La primera enciende inmediatamente; la segunda mantiene el encendido y la
tercera apaga. Se conserva el apagado automático de 30 segundos. Si la cámara
sigue renovando presencia, tiene prioridad y las tres palmadas no apagan la luz.
Se considera presencia actual una renovación de cámara en los últimos 1.5 s.
El sensor detecta pulsos por umbral, no reconoce acústicamente palmadas:
otros ruidos pueden contar y la sensibilidad del módulo afecta el resultado.

Firmware cargado en Arduino Uno COM3. Se usa `RELAY_ACTIVE_LEVEL = HIGH` según
la prueba del usuario: el foco enciende al llevar la entrada de control del
módulo al positivo. D3 sustituye esa señal manual de control.

- D2: servo, como antes.
- D3: señal de control de un módulo relé compatible con Arduino.
- D4: entrada digital del sensor de sonido instalado (requiere salida DO, no AO).

La tensión de red nunca se conecta a D3, D4 ni a la protoboard del Arduino.
El módulo y el montaje del lado de corriente alterna deben ser adecuados y
estar aislados y encerrados; encarga ese cableado a alguien cualificado.
No conectar una bobina de relé desnuda directamente al pin.

Una detección de rostro o persona renueva la luz cada 0.5 segundos. Arduino
mantiene el relé encendido durante 30 segundos desde la última presencia o
señal de sonido, sin bloquear la lectura del sensor ni el control del servo.
Al desaparecer la detección visual se envía una última renovación para dar
30 segundos completos de espera. Nunca se envía una orden de apagado por ausencia:
el temporizador es compartido con el sonido. Por ejemplo, persona en t=0 y
sonido en t=25 mantienen la luz hasta t=55, si no hay más detecciones.
La ventana muestra el estado lógico consultado a Arduino (`Luz D3: ON/OFF`)
y la terminal registra los cambios de presencia y de salida. Ese estado no
mide la luz del foco ni la alimentación del relé.
Cada inicio de pulso reconocido en D4 cuenta como un ruido. Un nivel fijo no
se repite y el regreso al reposo no cuenta como otro ruido. El umbral se ajusta en
el módulo; detecta ruido, no distingue personas. Sin sensor de luminosidad,
funciona también de día.

El sonido viene activado en modo `change`, tanto al iniciar Arduino como la
aplicación. Usa INPUT_PULLUP y toma el nivel inicial como reposo sin encender
la luz: conviene guardar silencio al arrancar. `--sound-sensor off` desactiva
la entrada hasta reiniciar Arduino. También admite `low` y `high` para
seleccionar explícitamente el nivel activo de cada pulso: LOW usa
INPUT_PULLUP; HIGH usa INPUT y el módulo debe mantener LOW en reposo.

Uso:

```bash
# Cámara, servo y luz por presencia, apagado 30 s después de la última detección:
bash start.sh --port COM3

# Cambiar tiempo de encendido; sonido por cambios digitales:
bash start.sh --port COM3 --light-seconds 60

# Luz y cámara sin mover el servo (sí abre el puerto USB para la luz):
bash start.sh --port COM3 --light --no-servo
```

Espacio pausa solo el servo. Al cerrar la aplicación, el servo se libera y la
luz se apaga al vencer su temporizador, salvo que haya nuevas señales de sonido.
La lectura de sonido habilitada continúa en Arduino sin depender del programa
de cámara. Reiniciar restaura sonido por cambios activado y
duración de 30 segundos. El estado eléctrico del relé durante el arranque de
la placa depende también del módulo; no está garantizado solo por software.

La luz está habilitada por defecto. `--no-light` omite las órdenes de luz de la
cámara y permite usar firmware anterior; no desactiva el sonido autónomo de un
Arduino con firmware nuevo. Se comprueba `LIGHT PING` antes de enviar órdenes.

Protocolo adicional (115200 baudios):

| Orden | Respuesta | Efecto |
| --- | --- | --- |
| LIGHT PING | OK LIGHT_1 | Comprobar soporte |
| LIGHT PERSON | OK LIGHT PERSON | Encender/renovar temporizador |
| LIGHT HOLD 30 | OK LIGHT HOLD 30 | Duración, de 1 a 3600 segundos |
| SOUND OFF | OK SOUND OFF | Desactivar entrada de sonido |
| SOUND CHANGE | OK SOUND CHANGE | Contar inicios de pulsos opuestos al reposo inicial |
| SOUND LOW | OK SOUND LOW | Contar pulsos activos en nivel bajo |
| SOUND HIGH | OK SOUND HIGH | Contar pulsos activos en nivel alto |
| SOUND STATS | OK SOUND N T | N ruidos y T triples reconocidos desde el arranque |
| SOUND READ | OK SOUND LOW / HIGH | Consultar el nivel digital actual de D4 |
| LIGHT STATE | OK LIGHT ON / OFF | Consultar estado lógico; no mide el foco |

`STOP` conserva su significado original: libera el servo, no apaga la luz.
Una pérdida de mensajes de cámara no mantiene la luz indefinidamente: el
temporizador vence localmente. La configuración no se guarda en EEPROM.

Pruebas sin dispositivos:

```bash
python3 -m unittest discover -s perip -p 'test_*.py'
g++ -std=c++11 -Wall -Wextra -Werror -I arduino/tests arduino/tests/test_light.cpp -o /tmp/camera_test_light
/tmp/camera_test_light
```

`arduino/upload.ps1 -CompileOnly` compila para Uno sin cargar la placa. El script
de carga incluye ahora también `light_control.h`.

## Diagnóstico del sensor de sonido

```bash
cd arduino
/mnt/c/Users/User/AppData/Local/Programs/Python/Python312/python.exe check_sound.py --port COM3 --seconds 40
```

Registra cada cambio de nivel en D4, el contador de ruidos que lleva el propio
Arduino y los cambios de estado de D3. Guarda silencio los primeros segundos: al
abrir el puerto la placa se reinicia y toma ese nivel como reposo. Después, una
palmada debe encender y tres palmadas seguidas apagar.

Cómo interpretar el resultado:

| Observación | Significado |
| --- | --- |
| `ruidos` sube con cada palmada | El sensor y el firmware funcionan. |
| D4 fijo en `HIGH` y `ruidos=0` | El pin está al aire: es el valor del pull-up interno. Revisar cableado y alimentación del módulo. |
| D4 fijo en `LOW` y `ruidos=0` | El módulo alimenta el pin pero nunca dispara. Ajustar el potenciómetro de umbral. |
| El LED de salida del módulo parpadea pero `ruidos` no sube | El problema está entre el módulo y D4, o falta masa común. |
| El LED de salida del módulo no parpadea | Umbral mal ajustado, o el cable sale de `AO` en vez de `DO`. |
| `ERR COMMAND` aislados | Corrupción en el enlace serie, no un fallo del sensor. El script aborta ante cualquier `ERR`. |

Prueba definitiva del pin, sin depender del módulo: toca D4 tres o cuatro veces
con un cable cuyo otro extremo esté en GND del Arduino, con medio segundo entre
toques. Si el contador de ruidos sube y D3 enciende, el pin, el firmware y el
relé están correctos y el fallo está en el módulo de sonido.

**Estado el 14 de septiembre de 2026:** 45 segundos de palmadas dieron 0 ruidos y
D4 constante en `HIGH`. En una medición anterior, con el mismo firmware, D4
reposaba en `LOW` y sí generó flancos que encendieron D3. La incidencia está
abierta y detallada en el [README](README.md#incidencias-abiertas).
