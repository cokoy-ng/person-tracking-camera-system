# Servo SG90 desde Python y VS Code / WSL

El firmware del Arduino Uno recibe órdenes por USB. Python decide cuándo mover
el servo; no hace falta abrir Arduino IDE. El ángulo solicitado no mide el ángulo
físico del motor y no elimina su límite mecánico.

## Ejecutar desde Ubuntu WSL

```bash
cd /home/tucu/yo/camera/arduino
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
- Arduino conectado por USB a Windows, detectado como COM3.
- Programa principal y entorno virtual en WSL Ubuntu, Python 3.12.
- Un proceso auxiliar del Python de Windows abre COM3 y comunica las órdenes y
  respuestas con Python de WSL mediante entrada/salida estándar. No abre puertos
  de red ni necesita usbipd. Usa la misma dependencia pyserial del venv.
- El script busca una única instalación de Python en Windows. Si hay varias,
  define ARDUINO_WINDOWS_PYTHON con la ruta Linux a su python.exe.
- Si se configura acceso USB nativo a WSL más adelante, usa
  `--port /dev/ttyACM0` para utilizar pyserial directamente sin puente.

No se integra aún la webcam: este proyecto prueba el control USB del Arduino.

## Cargar firmware desde la terminal

El firmware ya se cargó en la prueba inicial. Solo hay que repetir este paso si
se modifica el archivo .ino o se carga otro programa en la placa.

```bash
cd /home/tucu/yo/camera/arduino
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
