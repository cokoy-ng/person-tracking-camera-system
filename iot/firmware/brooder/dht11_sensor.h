#pragma once
#include <Arduino.h>

// Señal configurable (D2-D5 en el criadero). Protocolo de un solo cable del DHT11, escrito a mano (sin
// librerías externas). No leer más rápido que cada ~2 s: el sensor no
// responde bien a más frecuencia.
class DHT11Sensor {
 private:
  byte pin;
 public:
  byte diagnostic = 8; // 0 OK; 1 sin respuesta; 2/3 respuesta bloqueada;
                       // 4/5 datos incompletos; 6 checksum; 7 rango; 8 pendiente.
  explicit DHT11Sensor(byte sensorPin) : pin(sensorPin) {}
  bool read(int &humidity, int &temperature) {
    diagnostic = 1;
    byte data[5] = {0, 0, 0, 0, 0};
    pinMode(pin, OUTPUT);
    digitalWrite(pin, LOW);
    delay(18);
    digitalWrite(pin, HIGH);
    delayMicroseconds(30);
    pinMode(pin, INPUT_PULLUP);

    unsigned long timeout = micros();
    while (digitalRead(pin) == HIGH) if (micros() - timeout > 200) return false;
    diagnostic = 2;
    timeout = micros();
    while (digitalRead(pin) == LOW) if (micros() - timeout > 200) return false;
    diagnostic = 3;
    timeout = micros();
    while (digitalRead(pin) == HIGH) if (micros() - timeout > 200) return false;

    for (int i = 0; i < 40; i++) {
      diagnostic = 4;
      timeout = micros();
      while (digitalRead(pin) == LOW) if (micros() - timeout > 200) return false;
      unsigned long start = micros();
      diagnostic = 5;
      timeout = micros();
      while (digitalRead(pin) == HIGH) if (micros() - timeout > 200) return false;
      unsigned long width = micros() - start;
      data[i / 8] <<= 1;
      if (width > 40) data[i / 8] |= 1;
    }

    byte checksum = data[0] + data[1] + data[2] + data[3];
    diagnostic = 6;
    if (checksum != data[4]) return false;
    humidity = data[0];
    temperature = data[2];
    diagnostic = humidity <= 100 && temperature <= 50 ? 0 : 7;
    return diagnostic == 0;
  }
};
