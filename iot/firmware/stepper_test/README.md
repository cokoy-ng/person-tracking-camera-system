# Prueba independiente del 28BYJ-48 (5 V)

Este sketch controla únicamente el motor paso a paso mediante un driver con
entradas IN1–IN4 (secuencia para ULN2003). No utiliza librerías adicionales.

| Driver | Arduino Uno |
| --- | --- |
| IN1 | D8 |
| IN2 | D9 |
| IN3 | D10 |
| IN4 | D11 |
| GND | GND común con Arduino y la fuente del driver |

D9 es un pin digital; el Uno tiene entradas analógicas A0–A5, no A9.
El motor se conecta al driver. Alimenta el driver con 5 V adecuados para el
motor, nunca desde un pin de señal del Arduino.

1. Cierra el dashboard, tracking y cualquier programa que esté usando el COM.
2. Abre `stepper_test.ino` en Arduino IDE, selecciona Arduino Uno y el puerto
   actual, y carga el sketch.
3. Abre el monitor serie a **115200 baudios**. El motor inicia detenido.
4. Envía una letra por orden (con o sin salto de línea):

| Orden | Acción |
| --- | --- |
| `F` | Avanza 1024 medios pasos, aproximadamente un cuarto de vuelta. |
| `R` | Retrocede 1024 medios pasos. |
| `V` | Ordena 4096 medios pasos en aproximadamente 10 segundos (6 RPM). |
| `M` | Ordena seis vueltas seguidas: 24576 medios pasos en aproximadamente un minuto. |
| `N` | Seis vueltas en sentido inverso a M, también a 6 RPM. |
| `S` | Detiene el movimiento y desenergiza las cuatro entradas. |

La consigna actual es de 6 RPM. `OK DONE` confirma la secuencia eléctrica,
no el giro físico. Los tiempos y ángulos son aproximados.
Cada movimiento F/R dura aproximadamente 2,5 segundos. Al finalizar aparece
`OK DONE` y se desenergizan las bobinas; el eje queda sin retención eléctrica.
Durante un movimiento, otra orden F/R devuelve BUSY. S sigue disponible.
El sentido físico depende del motor y el cableado. Los ángulos son aproximados:
no hay sensor de posición y el software no detecta pasos perdidos.

También puedes compilar/cargar desde WSL usando `iot/host/upload_stepper.ps1`
con PowerShell de Windows. `-CompileOnly` compila sin cargar; para cargar,
indica `-Port COMx` con el puerto actual.

**Cargar esta prueba reemplaza el firmware que corre en el Arduino**, aunque
los archivos del proyecto principal se conservan. Mientras esté cargada,
`start.sh` y el dashboard no dispondrán del protocolo habitual. Para volver
al sistema original, carga `servo_usb` mediante `iot/host/upload.ps1`.
