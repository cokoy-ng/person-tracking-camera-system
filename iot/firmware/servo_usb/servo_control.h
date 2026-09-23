#pragma once
#include <Servo.h>
#include "pins.h"

// Señal D2. LED_BUILTIN refleja el estado para diagnóstico visual sin PC.
class ServoControl {
  Servo servo;
 public:
  void set(int angle) {
    if (!servo.attached()) servo.attach(PIN_SERVO);
    servo.write(angle);
    digitalWrite(LED_BUILTIN, angle > 0 ? HIGH : LOW);
  }
  void stop() {
    servo.detach();
    digitalWrite(LED_BUILTIN, LOW);
  }
  bool attached() { return servo.attached(); }
};
