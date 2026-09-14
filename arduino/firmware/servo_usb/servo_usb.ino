#include <Servo.h>
#include <stdlib.h>
#include <string.h>
#include "light_control.h"

Servo servo;
const int PIN_SERVO = 2;
const int PIN_RELAY = 3;
const int PIN_SOUND = 4;
// El usuario comprobó que la entrada del módulo enciende con positivo.
const int RELAY_ACTIVE_LEVEL = HIGH;
LightControl light;
bool soundEnabled = true;
bool soundChanges = true;
int previousSound = HIGH;
int soundActiveLevel = LOW;
int soundIdleLevel = HIGH;
SoundGesture soundGesture;

void updateLight() {
  int sound = digitalRead(PIN_SOUND);
  if (soundEnabled) {
    bool active = soundChanges ? sound != soundIdleLevel : sound == soundActiveLevel;
    int gesture = soundGesture.update(active, millis());
    if (gesture > 0) light.trigger(millis());
    else if (gesture < 0) light.soundOff(millis());
  }
  previousSound = sound;
  light.update(millis());
  digitalWrite(PIN_RELAY, light.on ? RELAY_ACTIVE_LEVEL : !RELAY_ACTIVE_LEVEL);
}
char line[32];
byte length = 0;
bool overflow = false;

void command() {
  if (strcmp(line, "PING") == 0) {
    Serial.println("PONG SERVO_USB_1");
  } else if (strcmp(line, "LIGHT PING") == 0) {
    Serial.println("OK LIGHT_1");
  } else if (strcmp(line, "SOUND READ") == 0) {
    Serial.println(digitalRead(PIN_SOUND) == HIGH ? "OK SOUND HIGH" : "OK SOUND LOW");
  } else if (strcmp(line, "SOUND STATS") == 0) {
    Serial.print("OK SOUND ");
    Serial.print(soundGesture.events);
    Serial.print(" ");
    Serial.println(soundGesture.triples);
  } else if (strcmp(line, "LIGHT STATE") == 0) {
    Serial.println(light.on ? "OK LIGHT ON" : "OK LIGHT OFF");
  } else if (strcmp(line, "LIGHT PERSON") == 0) {
    light.person(millis());
    Serial.println("OK LIGHT PERSON");
  } else if (strncmp(line, "LIGHT HOLD ", 11) == 0) {
    char *end;
    long seconds = strtol(line + 11, &end, 10);
    if (end == line + 11 || *end != '\0' || seconds < 1 || seconds > 3600) {
      Serial.println("ERR HOLD");
      return;
    }
    light.holdMs = (uint32_t)seconds * 1000;
    Serial.print("OK LIGHT HOLD ");
    Serial.println(seconds);
  } else if (strcmp(line, "SOUND OFF") == 0) {
    soundEnabled = false;
    Serial.println("OK SOUND OFF");
  } else if (strcmp(line, "SOUND CHANGE") == 0) {
    pinMode(PIN_SOUND, INPUT_PULLUP);
    previousSound = digitalRead(PIN_SOUND);
    soundIdleLevel = previousSound;
    soundGesture.reset(false);
    soundChanges = true;
    soundEnabled = true;
    Serial.println("OK SOUND CHANGE");
  } else if (strcmp(line, "SOUND LOW") == 0 || strcmp(line, "SOUND HIGH") == 0) {
    soundChanges = false;
    soundActiveLevel = strcmp(line, "SOUND LOW") == 0 ? LOW : HIGH;
    pinMode(PIN_SOUND, soundActiveLevel == LOW ? INPUT_PULLUP : INPUT);
    soundGesture.reset(digitalRead(PIN_SOUND) == soundActiveLevel);
    soundEnabled = true;
    Serial.print("OK ");
    Serial.println(line);
  } else if (strcmp(line, "STOP") == 0) {
    servo.detach();
    digitalWrite(LED_BUILTIN, LOW);
    Serial.println("OK STOP");
  } else if (strncmp(line, "SET ", 4) == 0) {
    char *end;
    long angle = strtol(line + 4, &end, 10);
    if (end == line + 4 || *end != '\0' || angle < 0 || angle > 180) {
      Serial.println("ERR ANGLE");
      return;
    }
    // Match the working Arduino sketch: attach D2 before writing the angle.
    if (!servo.attached()) servo.attach(PIN_SERVO);
    servo.write((int)angle);
    digitalWrite(LED_BUILTIN, angle > 0 ? HIGH : LOW);
    Serial.print("OK ");
    Serial.println(angle);
  } else {
    Serial.println("ERR COMMAND");
  }
}

void setup() {
  digitalWrite(PIN_RELAY, !RELAY_ACTIVE_LEVEL);
  pinMode(PIN_RELAY, OUTPUT);
  pinMode(PIN_SOUND, INPUT_PULLUP);
  previousSound = digitalRead(PIN_SOUND);
  soundIdleLevel = previousSound;
  soundGesture.reset(false);
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);
  Serial.begin(115200);
  Serial.println("READY SERVO_USB_1");
}

void loop() {
  updateLight();
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      line[length] = '\0';
      if (overflow) Serial.println("ERR LENGTH");
      else command();
      length = 0;
      overflow = false;
    } else if (length < sizeof(line) - 1) {
      line[length++] = c;
    } else {
      overflow = true;
    }
    updateLight();
  }
}
