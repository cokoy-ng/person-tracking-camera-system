# Control autónomo del criadero

Firmware independiente para Arduino Uno. Sustituye temporalmente el firmware
serie de cámara/dashboard; `start.sh` no utiliza este protocolo.

| Elemento | Pin |
| --- | --- |
| Alarma con activación HIGH | A0 |
| Señal del DHT11 previamente conectado a D5 | A1 |
| Foquito/orden de calefacción, activación HIGH | A2 |
| Driver 28BYJ-48 IN1–IN4 | D8–D11 |

A1 utiliza el protocolo digital DHT11, no una conversión de `analogRead`.
La salida A2 representa calefacción; el foquito de prueba no calienta el recinto.
La alarma se controla por nivel HIGH (buzzer activo/módulo); un buzzer pasivo
necesitaría generación de tono. Las polaridades se configuran en `config.h`.

## Control

- Lectura cada 2,5 segundos; temperatura y humedad por serie a 115200 baudios.
- Menos de 26 °C: calefacción encendida. Se apaga desde 30 °C para evitar
  conmutaciones repetidas cerca de 26 °C.
- Alarma fuera de 26–32 °C, ante fallo del sensor o posición desconocida.
- Fallo de lectura o muestra caducada (6 s): calefacción apagada, motor
  desenergizado. Una lectura válida permite recuperar el control.
- Al inicio, puerta abierta: si la lectura es de 32 °C o menos, cierra.
  Si empieza por encima de 32 °C, permanece abierta.
- Puerta cerrada: abre solamente después de **más de 5 minutos seguidos por
  encima de 32 °C**. Una lectura de 32 °C o menos reinicia el temporizador
  y solicita cierre. Una lectura inválida, caducada o STOP reinicia la espera.
  La alarma térmica sigue siendo inmediata; no espera esos 5 minutos.
- El cambio de objetivo se evalúa cada 2,5 s; el giro se detiene al alcanzar
  el extremo. No se repiten las 12 vueltas por cada lectura.
- Recorrido completo: 49152 medios pasos, aproximadamente 12 vueltas a
  6 RPM (2 minutos). No repite recorridos si ya está en el extremo solicitado.
  Si cambia el objetivo a mitad de recorrido, vuelve desde la posición contada.
- Sentido original de las pruebas = cerrar; inverso = enrollar/abrir.
  Cambiar `CLOSE_DIRECTION` si el montaje físico tiene el sentido opuesto.

## Posición y parada

No se han declarado finales de carrera. La posición es una estimación por
pasos, no una medición: si patina, se atasca o se mueve manualmente, hay que
referenciar de nuevo. No hay detección de obstáculos.

Se guarda en EEPROM el extremo al terminar. Antes de mover se marca posición
incierta: reiniciar durante el movimiento bloquea el motor y pide referencia.
El arranque inicial necesita confirmar la posición; en esta instalación el
usuario indicó puerta completamente enrollada/abierta.

Comandos de una letra por monitor serie, terminados en salto de línea:

| Orden | Acción |
| --- | --- |
| `?` | Estado, posición/objetivo en medios pasos, calefacción y alarma. |
| `S` | Detiene motor y calefacción; alarma sigue disponible. |
| `A` | Retoma el control automático. |
| `O` | Confirma físicamente puerta completamente abierta; no mueve el motor. |
| `C` | Confirma físicamente puerta completamente cerrada; no mueve el motor. |

Para referenciar manualmente: `S`, colocar físicamente en un extremo, `O` o
`C`, luego `A`. Abrir el puerto serie puede reiniciar el Uno. Cerrar el
monitor no detiene el control autónomo.

## Carga y pruebas

`iot/host/upload_brooder.ps1 -Port COM3`, ejecutado con PowerShell Windows,
compila y carga; comprobar el COM actual. `-CompileOnly` solo compila.

```bash
g++ -std=c++11 -Wall -Wextra -Werror iot/firmware-tests/test_brooder.cpp -o /tmp/test_brooder
/tmp/test_brooder
```

Las pruebas cubren umbrales, histéresis, muestras inválidas/caducadas,
desbordamiento del reloj, extremos, inversión parcial, conteo de 12 vueltas,
arranque abierto y espera de más de 5 minutos de calor continuo.
El rango 26–32 es el solicitado; no garantiza mantener esa temperatura sin
capacidad suficiente de calefacción/ventilación. Antes de sustituir el
foquito por calefacción real, verificar polaridad del relé y disponer de un
corte térmico independiente del software.

## Inicio de una nueva sesión desde abierta

Con la puerta **físicamente abierta**, ejecutar con Python Windows:

```text
python iot/diagnostics/start_brooder.py --port COM3
```

Este inicio envía STOP, confirma referencia ABIERTA y activa AUTO. Con una
lectura <=32 °C comienza el cierre de 12 vueltas; con >32 °C permanece abierta.
No usar este comando para consultar el estado de una puerta cerrada: la
referencia debe corresponder a la posición física. Para solo reanudar se usa A.
Los reinicios eléctricos conservan el extremo guardado en EEPROM o bloquean
si se interrumpió un movimiento, para no repetir recorridos accidentalmente.

El script usa tramas `~S53`, `~O4F`, `~A41` con comprobación del byte de comando,
y espera confirmación de cada una. Un comando corrupto se rechaza. Si falla
la confirmación durante un movimiento, observar estado antes de reiniciar:
no volver a asignar abierta mientras el motor ya está cerrando.
