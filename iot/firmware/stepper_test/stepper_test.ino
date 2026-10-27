// Prueba independiente del 28BYJ-48 de 5 V con driver tipo ULN2003.
// IN1 -> D8, IN2 -> D9, IN3 -> D10, IN4 -> D11.
// Monitor serie: 115200 baudios. No arranca hasta recibir una orden.
#include <Arduino.h>

const byte MOTOR_PINS[] = {8, 9, 10, 11};
const byte HALF_STEPS[8][4] = {
  {1, 0, 0, 0}, {1, 1, 0, 0}, {0, 1, 0, 0}, {0, 1, 1, 0},
  {0, 0, 1, 0}, {0, 0, 1, 1}, {0, 0, 0, 1}, {1, 0, 0, 1}
};
// 60 000 000 us / (4096 medios pasos por vuelta * 6 RPM).
const unsigned long STEP_INTERVAL_US = 2441;
// Aproximadamente 1/4 de vuelta; la reductora puede variar entre modelos.
const unsigned int TEST_STEPS = 1024;
unsigned int remaining = 0;
unsigned long lastStep = 0;
int phase = 7;
int direction = 1;

void releaseMotor() {
  remaining = 0;
  for (byte i = 0; i < 4; ++i) digitalWrite(MOTOR_PINS[i], LOW);
}

void startMove(int requestedDirection, unsigned int steps = TEST_STEPS) {
  if (remaining) {
    Serial.println(F("BUSY: pulsa S para detener"));
    return;
  }
  direction = requestedDirection;
  remaining = steps;
  lastStep = micros();
  Serial.println(direction > 0 ? F("MOVING FORWARD") : F("MOVING REVERSE"));
}

void setup() {
  for (byte i = 0; i < 4; ++i) {
    digitalWrite(MOTOR_PINS[i], LOW);
    pinMode(MOTOR_PINS[i], OUTPUT);
  }
  Serial.begin(115200);
  Serial.println(F("READY STEPPER_TEST_1"));
  Serial.println(F("F: avance 1024 medios pasos | R: retroceso | S: parar y liberar"));
  Serial.println(F("V: una vuelta aproximada (4096 medios pasos)"));
  Serial.println(F("M: seis vueltas aproximadas en un minuto"));
  Serial.println(F("N: seis vueltas en sentido inverso"));
}

void loop() {
  // Sin delay: permite atender STOP entre pasos.
  if (Serial.available()) {
    char command = Serial.read();
    switch (command) {
      case 'F': case 'f': startMove(1); break;
      case 'R': case 'r': startMove(-1); break;
      case 'V': case 'v': startMove(1, 4096); break;
      case 'M': case 'm': startMove(1, 24576); break;
      case 'N': case 'n': startMove(-1, 24576); break;
      case 'S': case 's':
        releaseMotor();
        Serial.println(F("OK STOP"));
        break;
      case '\r': case '\n': case ' ': break;
      default: Serial.println(F("ERR: usa F, R, V, M, N o S")); break;
    }
  }
  unsigned long now = micros();
  if (remaining && now - lastStep >= STEP_INTERVAL_US) {
    lastStep = now;
    phase = (phase + direction + 8) % 8;
    for (byte i = 0; i < 4; ++i) {
      digitalWrite(MOTOR_PINS[i], HALF_STEPS[phase][i] ? HIGH : LOW);
    }
    if (--remaining == 0) {
      releaseMotor();
      Serial.println(F("OK DONE"));
    }
  }
}
