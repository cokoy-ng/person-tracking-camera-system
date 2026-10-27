#pragma once
#include <Arduino.h>

// Señal configurable (A1 en el criadero). Protocolo de un solo cable del DHT11, escrito a mano (sin
// librerías externas). No leer más rápido que cada ~2 s: el sensor no
// responde bien a más frecuencia.
class DHT11Sensor {
 private:
  byte pin;
 public:
  explicit DHT11Sensor(byte sensorPin) : pin(sensorPin) {}
  bool read(int &humidity, int &temperature) {
    byte data[5] = {0, 0, 0, 0, 0};
    pinMode(pin, OUTPUT);
    digitalWrite(pin, LOW);
    delay(18);
    digitalWrite(pin, HIGH);
    delayMicroseconds(30);
    pinMode(pin, INPUT_PULLUP);

    unsigned long timeout = micros();
    while (digitalRead(pin) == HIGH) if (micros() - timeout > 200) return false;
    timeout = micros();
    while (digitalRead(pin) == LOW) if (micros() - timeout > 200) return false;
    timeout = micros();
    while (digitalRead(pin) == HIGH) if (micros() - timeout > 200) return false;

    for (int i = 0; i < 40; i++) {
      timeout = micros();
      while (digitalRead(pin) == LOW) if (micros() - timeout > 200) return false;
      unsigned long start = micros();
      timeout = micros();
      while (digitalRead(pin) == HIGH) if (micros() - timeout > 200) return false;
      unsigned long width = micros() - start;
      data[i / 8] <<= 1;
      if (width > 40) data[i / 8] |= 1;
    }

    byte checksum = data[0] + data[1] + data[2] + data[3];
    if (checksum != data[4]) return false;
    humidity = data[0];
    temperature = data[2];
    return humidity <= 100 && temperature <= 50;
  }
};
