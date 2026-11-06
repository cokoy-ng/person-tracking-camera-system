> **Vigente:** BROODER_16_MANUAL_PUMP. **D7 motobomba SOLO MANUAL**, sin automatismo por humedad ni cambio de ciclo. D8 ventilador y D9 calefacción conservan automático. [Reglas actuales](PIN_REMAP_2026_11_04.md#vigente-brooder_16_manual_pump--bomba-exclusivamente-manual).

> **Vigente:** BROODER_15_AUTO_CYCLES arranca en automático; al cambiar la señal D2–D5 adapta rangos y devuelve las salidas de clima a automático. STOP explícito se respeta. [Reglas actuales](PIN_REMAP_2026_11_04.md#vigente-brooder_15_auto_cycles--adaptación-automática).

> **Vigente:** BROODER_14_PHYSICAL_CYCLES: un DHT11 en D2/D3/D4/D5 selecciona físicamente ciclo1/2/3/4. No hay selección por botones ni sensor fijo D5. [Rangos y estado actual](PIN_REMAP_2026_11_04.md#versión-vigente-brooder_14_physical_cycles).

> **Vigente:** BROODER_13_MANUAL_DOOR, manual independiente de pausa y controles de puerta. Ver [estado y reglas actuales](PIN_REMAP_2026_11_04.md#corrección-manual-y-puerta--versión-vigente-brooder_13_manual_door). D7/D8/D9 configurados LOW; polaridad física de D9 pendiente de confirmar.

> **2026-11-04:** BROODER_12 cargado en COM6; sensor D5 verificado, actuadores pendientes de observación física. Consultar [nuevo cableado y pendientes](PIN_REMAP_2026_11_04.md). Las referencias a pines inferiores describen la versión anterior.

# Criadero autónomo — BROODER_9_THREE_AIR

Un único DHT11. Mover **solo su señal** entre D2, D3, D4 o D5 selecciona
manualmente la etapa. A1 ya no se lee ni se utiliza. No se calcula edad/fecha.
Los rangos son los indicados por el usuario, no una recomendación de crianza.

| Señal | Etapa | Temperatura | Humedad | Centro T / HR |
|---|---|---|---|---|
| D2 | Días 1–3 | 33–34 °C | 60–70 % | 33,5 °C / 65 % |
| D3 | Días 4–7 | 30–32 °C | 50–65 % | 31 °C / 57,5 % |
| D4 | Días 8–14 | 27–29 °C | 50–60 % | 28 °C / 55 % |
| D5 | Días 15–21 | 24–27 °C | 50–60 % | 25,5 °C / 55 % |

- D7: orden HIGH del ventilador interno que pasa aire sobre agua y aumenta HR.
- A4: orden HIGH de extracción. A5: orden HIGH de entrada de aire exterior.
- A2: orden HIGH de calefacción/foco. A0: pulsos de alarma activa HIGH.
- Driver motor: D8–D11. D0/D1 reservados a USB/serie. A3 queda libre.
- D7 y A2–A5 son señales para controladores/relés, no alimentación directa de cargas.

## Regulación

Calefacción: margen alrededor del centro de ±0,25 °C en ciclo1 y ±0,5 °C
en los otros. ON al alcanzar/bajar del borde inferior, OFF al alcanzar/subir
del superior. Entre bordes conserva estado. Permanencia mínima de 10 s.
Humidificación D7: ON a centroHR−2 puntos y OFF al llegar al centro, permanencia
mínima 15 s. Extracción A4 y entrada A5 trabajan juntas: ON por T≥borde superior
del control o HR≥centro+2; OFF al volver a los centros. A4/A5 se bloquean a
T≤mínimo para evitar enfriar más. Los límites críticos omiten la espera.
STOP y fallo apagan calefacción y las tres salidas de aire inmediatamente.
El DHT11 actual entrega enteros; el centro es referencia, no precisión garantizada.
No es un PID calibrado ni puede garantizar el ambiente sin capacidad física suficiente.

Se escanean los cuatro pines cada 2,5 s y se exigen dos lecturas válidas
consecutivas de un único pin. Sin respuesta, más de un sensor o señal inválida:
calefacción y D7/A4/A5 OFF, con motor detenido. El ciclo queda sin confirmar.
Cambiar ciclo reinicia estados de regulación y espera de puerta; la selección
se conserva físicamente por el cable, no mediante fecha o EEPROM.

Puerta: cierra a T≤máximo del ciclo; abre después de más de 5 minutos
continuos por encima del máximo. Cambio de ciclo, fallo y STOP reinician esa
espera. Recorrido 49152 medios pasos (12 vueltas) a 6 RPM; posición estimada,
sin finales de carrera. La lectura secuencial DHT pausa brevemente los pasos.

## Alarmas sin aviso continuo

Fuera de los límites de temperatura/HR durante 30 s: alerta confirmada.
Fallo de sensor/ciclo o posición desconocida durante 10 s: alerta confirmada.
Lecturas transitorias no producen aviso sonoro. Recuperación: 15 s estables
antes de borrar la alerta, pero no suena cuando la condición ya desapareció.
Salida A0: pulso de 1 s al confirmar y luego cada 60 s mientras persista.
No se cambia el modelo físico de buzzer: una salida HIGH no garantiza sonido.

`STATE alarm` representa alerta confirmada, no el nivel instantáneo de A0.
`ALERT sounding` informa el pulso; pending/recovering distinguen confirmación
inicial y recuperación. Bits reasons: 1 T baja, 2 T alta, 4 HR baja, 8 HR alta,
16 sensor/ciclo sin confirmar, 32 puerta sin referencia. Al cambiar de etapa
confirmada se reinicia la alerta anterior.

## Serie y dashboard

115200 baudios. `TEMP`, `CYCLE`, `ALERT`, `STATE` se envían por serie.
CYCLE contiene id, pin, humidifier(D7), exhaust(A4), intake(A5) y reason.
Dashboard: `bash start.sh --dashboard --port COM3`, http://localhost:5173.
El backend escucha sin ordenar movimientos. Cerrar dashboard antes de cargar
firmware o acceder a serie desde otro proceso.

Comandos: S STOP motor/calefacción/los tres ventiladores, A AUTO, ? estado,
O referencia físicamente abierta, C referencia físicamente cerrada.
También tramas verificadas ~S53, ~A41, ~?3F. Nunca falsear referencia para mover.
EEPROM conserva extremos. Si se reinicia en movimiento queda sin referencia.
STOP es volátil: reset vuelve a AUTO cuando haya sensor/ciclo confirmado.

El LCD fue retirado del firmware principal. D7, A4 y A5 están dedicados al nuevo
sistema de aireación. El sistema puede funcionar sin PC con alimentación externa.

## Verificación

```
g++ -std=c++11 -Wall -Wextra -Werror iot/firmware-tests/test_brooder.cpp -o /tmp/test_brooder
/tmp/test_brooder
python3 -m unittest discover -s backend -p 'test_*.py' -v
```

Cargador: iot/host/upload_brooder.ps1 -CompileOnly o -Port COM3 (Python/CLI Windows).
Validado control en C++, parser backend, build/lint frontend y escenarios UI
simulados de cuatro ciclos/alarmas/fallo/caducidad. Pruebas físicas de giro,
humidificación, calefacción real y precisión alrededor del centro quedan a validar.
