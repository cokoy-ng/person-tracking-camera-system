# Servo, relé de luz y sensor de sonido desde Python y VS Code / WSL

El firmware del Arduino Uno recibe órdenes por USB. Python decide cuándo mover
el servo; no hace falta abrir Arduino IDE. El ángulo solicitado no mide el ángulo
físico del motor y no elimina su límite mecánico.

La misma placa controla además un relé de luz en D3 y lee un sensor de sonido en
D4, con un temporizador que corre de forma autónoma en el Arduino. Esa parte se
documenta en [LIGHT_CONTROL.md](../LIGHT_CONTROL.md).

## Ejecutar desde Ubuntu WSL

```bash
cd /home/tucu/yo/person-tracking-camera-system/arduino
source .venv/bin/activate
python servo.py --demo
```

Alterna las órdenes 0 y 90 cada segundo. El LED integrado L se apaga en 0 y se
enciende en 90. Ctrl+C termina el programa y libera el servo (deja de enviarle
pulsos, por lo que deja de sostener activamente la posición).

```bash
python servo.py --check             # Verificar respuesta del firmware
python servo.py --angle 90          # Ordenar 90, esperar 1 s y liberar
python servo.py --demo --cycles 3   # Tres ciclos y terminar
python servo.py --port COM3 --demo # Elegir puerto de Windows
```

Solo un programa puede usar el puerto a la vez. Cierra el monitor serie y termina
la demo antes de ejecutar otro comando o cargar firmware.

## Conexión usada en este equipo

- Señal del servo: D2; alimentación del circuito: 5V y GND.
- Señal de control del módulo relé: D3, activo en HIGH.
- Salida digital DO del módulo de sonido: D4, leída con `INPUT_PULLUP`.
- La tensión de red nunca se conecta a D3, D4 ni a la protoboard.
- Arduino conectado por USB a Windows, detectado como COM3.
- Programa principal y entorno virtual en WSL Ubuntu, Python 3.12.
- Un proceso auxiliar del Python de Windows abre COM3 y comunica las órdenes y
  respuestas con Python de WSL mediante entrada/salida estándar. No abre puertos
  de red ni necesita usbipd. Usa la misma dependencia pyserial del venv.
- El script busca una única instalación de Python en Windows. Si hay varias,
  define ARDUINO_WINDOWS_PYTHON con la ruta Linux a su python.exe.
- Si se configura acceso USB nativo a WSL más adelante, usa
  `--port /dev/ttyACM0` para utilizar pyserial directamente sin puente.

Esta carpeta cubre el control USB del Arduino. La integración con la cámara y
los modelos de visión está en [`perip/`](../perip/README.md) y se arranca con
`start.sh` desde la raíz del proyecto.

## Diagnóstico del sensor de sonido

```bash
cd /home/tucu/yo/person-tracking-camera-system/arduino
/mnt/c/Users/User/AppData/Local/Programs/Python/Python312/python.exe check_sound.py --port COM3 --seconds 40
```

Muestra el nivel de D4, el contador de ruidos que lleva el propio Arduino y el
estado lógico de D3, sin abrir la cámara. La tabla de interpretación está en
[LIGHT_CONTROL.md](../LIGHT_CONTROL.md#diagnóstico-del-sensor-de-sonido).

## Cargar firmware desde la terminal

El firmware ya se cargó en la prueba inicial. Solo hay que repetir este paso si
se modifica el archivo .ino o se carga otro programa en la placa.

```bash
cd /home/tucu/yo/person-tracking-camera-system/arduino
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w "$PWD/upload.ps1")" -Port COM3
```

`upload.ps1` utiliza arduino-cli de la instalación existente, copia el firmware a
una carpeta temporal de Windows, compila para arduino:avr:uno y carga con
verificación. No inicia la interfaz de Arduino IDE.

## Recrear el entorno

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

En VS Code selecciona `arduino/.venv/bin/python` como intérprete en la ventana WSL.

## Protocolo

115200 baudios, líneas ASCII terminadas en salto de línea:

| Orden | Respuesta |
| --- | --- |
| PING | PONG SERVO_USB_1 |
| SET 90 | OK 90 |
| STOP | OK STOP |

SET acepta enteros de 0 a 180. Las órdenes inválidas reciben ERR y no cambian la
posición. OK confirma que el Arduino procesó la orden, no que se haya medido el
movimiento del eje. Al reiniciarse la placa, espera órdenes sin activar el servo.
`STOP` libera el servo; no apaga la luz.

Las órdenes `LIGHT ...` y `SOUND ...` del control de luz se documentan en
[LIGHT_CONTROL.md](../LIGHT_CONTROL.md).

Medición del 14 de septiembre de 2026: de 600 `PING` consecutivos, 3 recibieron
`ERR COMMAND`. Un `PING` no puede fallar por lógica, así que hay corrupción en el
enlace serie. Está registrado como incidencia abierta en el
[README principal](../README.md#incidencias-abiertas).
