#pragma once
const byte ALARM_PIN = A0;
const byte TEMPERATURE_PIN = A1;
const byte HEATER_PIN = A2;
const byte MOTOR_PINS[] = {8, 9, 10, 11};
const int ALARM_ACTIVE = HIGH;
const int HEATER_ACTIVE = HIGH;
// Sentido original de las pruebas = cerrar; inverso = enrollar/abrir.
const int CLOSE_DIRECTION = 1;
const unsigned long STEP_INTERVAL_US = 2441;
