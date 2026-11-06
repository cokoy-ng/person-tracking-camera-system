# Prueba aislada de LCD 1602A — Arduino Uno dedicado

SDA A4, SCL A5, VCC5V y GND. Solo LCD conectado a esta placa.
No cargar este sketch en la placa que controla el criadero.
Puerto detectado el 2026-10-31: COM6 (nuevo Uno); el criadero usaba COM3.

Es I2CexpDiag de hd44780 1.3.2 (Bill Perry), sin modificar. Usa Wire nativo,
autodetecta direccion/mapa/polaridad, comprueba bus/pullups y memoria LCD,
prueba retroiluminacion y deja un contador si logra inicializar.
Fuente: https://github.com/duinoWitchery/hd44780/tree/1.3.2/examples/ioClass/hd44780_I2Cexp/I2CexpDiag
Licencia GPLv3 conservada en LICENSE.txt y cabecera original.
Biblioteca: Arduino CLI `lib install hd44780@1.3.2` (ya instalada en Windows).

Carga: iot/host/upload_lcd_test.ps1 -Port COM6 (PowerShell Windows).
Solo compilar: -CompileOnly.
Lectura: Python Windows iot/diagnostics/check_lcd.py --port COM6 --reset --seconds 30.
9600 baudios, no 115200 del criadero. --reset solo para la placa dedicada.

Un ACK de direccion no confirma que el panel funcione. La prueba de memoria
comprueba el controlador LCD; luz/texto requieren confirmacion visual.
Imagenes de referencia: iot/images/delante-lcd.jpeg e iot/images/atras-lcd.jpeg.
