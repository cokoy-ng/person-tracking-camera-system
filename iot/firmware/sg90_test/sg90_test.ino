#include <Servo.h>
#include <stdlib.h>
#include <string.h>

// Giro continuo: los pulsos indican sentido/velocidad, nunca posición.
const byte SERVO_PIN = 2;
const int NEUTRAL_US = 1500;  // Pendiente calibrar si existe deriva.
const int FORWARD_US = 1600;
const int REVERSE_US = 1200;  // 1400 no produjo giro según observación física.
const unsigned long WAIT_MS = 3000;
const unsigned long SETTLE_MS = 300;
Servo motor;
char line[32];
byte used = 0;
bool overflow = false;
byte phase = 0;
unsigned long phaseStart = 0;
unsigned long runMs = 200;

void pulse(int us) {
  motor.writeMicroseconds(us);
  if (!motor.attached()) motor.attach(SERVO_PIN, 1000, 2000);
}

void stopServo() {
  phase = 0;
  motor.detach();
  digitalWrite(SERVO_PIN, LOW);
}

void updateCycle() {
  unsigned long elapsed = millis() - phaseStart;
  if (phase == 5 && elapsed >= runMs) {
    pulse(NEUTRAL_US);
    phase = 4;
    phaseStart = millis();
  } else if (phase == 1 && elapsed >= runMs) {
    pulse(NEUTRAL_US);
    phase = 2;
    phaseStart = millis();
    Serial.println(F("PHASE WAIT 3000"));
  } else if (phase == 2 && elapsed >= WAIT_MS) {
    pulse(REVERSE_US);
    phase = 3;
    phaseStart = millis();
    Serial.println(F("PHASE REVERSE"));
  } else if (phase == 3 && elapsed >= runMs) {
    pulse(NEUTRAL_US);
    phase = 4;
    phaseStart = millis();
    Serial.println(F("PHASE NEUTRAL"));
  } else if (phase == 4 && elapsed >= SETTLE_MS) {
    stopServo();
    Serial.println(F("OK DONE"));
  }
}

void command() {
  if (strcmp(line, "PING") == 0) {
    Serial.println(F("PONG SG90_CONTINUOUS_3"));
  } else if (strcmp(line, "STOP") == 0) {
    stopServo();
    Serial.println(F("OK STOP"));
  } else if (strncmp(line, "TURN ", 5) == 0) {
    if ((line[5] != 'R' && line[5] != 'L') || line[6] != ' ') {
      Serial.println(F("ERR DIRECTION"));
      return;
    }
    char *end;
    long duration = strtol(line + 7, &end, 10);
    if (end == line + 7 || *end || duration < 20 || duration > 5000) {
      Serial.println(F("ERR DURATION 20..5000"));
      return;
    }
    if (phase) {
      Serial.println(F("ERR BUSY"));
      return;
    }
    runMs = duration;
    pulse(line[5] == 'R' ? FORWARD_US : REVERSE_US);
    phase = 5;
    phaseStart = millis();
    Serial.println(F("OK TURN"));
  } else if (strncmp(line, "CYCLE ", 6) == 0) {
    char *end;
    long duration = strtol(line + 6, &end, 10);
    if (end == line + 6 || *end || duration < 50 || duration > 500) {
      Serial.println(F("ERR DURATION 50..500"));
      return;
    }
    if (phase) {
      Serial.println(F("ERR BUSY"));
      return;
    }
    runMs = duration;
    pulse(FORWARD_US);
    phase = 1;
    phaseStart = millis();
    Serial.println(F("OK CYCLE"));
    Serial.println(F("PHASE FORWARD"));
  } else {
    // SET retirado: este dispositivo no permite ordenar ángulos.
    Serial.println(F("ERR COMMAND"));
  }
}

void setup() {
  pinMode(SERVO_PIN, OUTPUT);
  digitalWrite(SERVO_PIN, LOW);
  Serial.begin(115200);
  Serial.println(F("READY SG90_CONTINUOUS_3 PIN=2"));
}

void loop() {
  updateCycle();
  // Limitar el trabajo serie para no retrasar el fin de un pulso.
  for (byte budget = 0; budget < 32 && Serial.available(); ++budget) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      line[used] = '\0';
      if (overflow) Serial.println(F("ERR LENGTH"));
      else if (used) command();
      used = 0;
      overflow = false;
    } else if (used < sizeof(line) - 1 && !overflow) {
      line[used++] = c;
    } else {
      overflow = true;
    }
  }
}
