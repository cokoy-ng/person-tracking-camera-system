#pragma once
#include "cycles.h"
const byte ALARM_PIN = A0;
// Un unico DHT11: D2/D3/D4/D5 seleccionan ciclos 1/2/3/4.
const byte SERVO_PIN = 6; // write(180), espera10s+3s, write(130), espera9s.
const byte UNUSED_PIN = 255;
const byte HUMIDIFIER_FAN_PIN = 7;  // Motobomba solo manual, nunca se enciende por HR ni al cambiar ciclo.
const byte EXHAUST_FAN_PIN = 8;     // Señal del unico ventilador.
const byte INTAKE_FAN_PIN = UNUSED_PIN; // No hay segunda salida de aire; A1-A5 libres.
const int FAN_ACTIVE = LOW; // Bomba y ventilador: relés activos en LOW, según ejemplo del usuario.
const byte HEATER_PIN = 9;
const byte MOTOR_PINS[] = {10, 11, 12, 13};
const bool DOOR_ENABLED = true;
const bool DOOR_AUTO_ENABLED = false; // Solo movimientos manuales con referencia confirmada.
const int ALARM_ACTIVE = HIGH;
const int HEATER_ACTIVE = LOW; // Mismo tipo de relé LOW; confirmar físicamente D9 antes de habilitar carga.
// Sentido original de las pruebas = cerrar; inverso = enrollar/abrir.
const int CLOSE_DIRECTION = 1;
const unsigned long STEP_INTERVAL_US = 2441;
