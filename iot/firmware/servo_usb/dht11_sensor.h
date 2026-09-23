#pragma once
#include "pins.h"

// Señal D5. Protocolo de un solo cable del DHT11, escrito a mano (sin
// librerías externas). No leer más rápido que cada ~2 s: el sensor no
// responde bien a más frecuencia.
class DHT11Sensor {
 public:
  bool read(int &humidity, int &temperature) {
    byte data[5] = {0, 0, 0, 0, 0};
    pinMode(PIN_DHT, OUTPUT);
    digitalWrite(PIN_DHT, LOW);
    delay(18);
    digitalWrite(PIN_DHT, HIGH);
    delayMicroseconds(30);
    pinMode(PIN_DHT, INPUT_PULLUP);

    unsigned long timeout = micros();
    while (digitalRead(PIN_DHT) == HIGH) if (micros() - timeout > 200) return false;
    timeout = micros();
    while (digitalRead(PIN_DHT) == LOW) if (micros() - timeout > 200) return false;
    timeout = micros();
    while (digitalRead(PIN_DHT) == HIGH) if (micros() - timeout > 200) return false;

    for (int i = 0; i < 40; i++) {
      timeout = micros();
      while (digitalRead(PIN_DHT) == LOW) if (micros() - timeout > 200) return false;
      unsigned long start = micros();
      timeout = micros();
      while (digitalRead(PIN_DHT) == HIGH) if (micros() - timeout > 200) return false;
      unsigned long width = micros() - start;
      data[i / 8] <<= 1;
      if (width > 40) data[i / 8] |= 1;
    }

    byte checksum = data[0] + data[1] + data[2] + data[3];
    if (checksum != data[4]) return false;
    humidity = data[0];
    temperature = data[2];
    return true;
  }
};
