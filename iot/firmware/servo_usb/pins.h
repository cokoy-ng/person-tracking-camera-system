#pragma once

// Mapa único de pines del Arduino Uno. Cualquier módulo nuevo debe declarar
// su pin aquí primero, para detectar choques antes de subir el firmware.
// D0/D1 están reservados por Serial (el puerto USB); nunca asignarlos.
const int PIN_SERVO = 2;  // SG90, señal PWM
const int PIN_RELAY = 3;  // Relé de la luz, activo en HIGH
const int PIN_SOUND = 4;  // Salida digital DO del sensor de sonido
const int PIN_DHT = 5;    // DHT11, protocolo de un solo cable
