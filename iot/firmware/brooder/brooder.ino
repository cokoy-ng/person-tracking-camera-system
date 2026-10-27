#include <Arduino.h>
#include <EEPROM.h>
#include "config.h"
#include "control.h"
#include "door.h"
#include "protocol.h"
#include "dht11_sensor.h"

ClimateControl control;
Door door;
DoorPolicy doorPolicy;
DHT11Sensor sensor(TEMPERATURE_PIN);
const byte PATTERN[8][4] = {
  {1,0,0,0},{1,1,0,0},{0,1,0,0},{0,1,1,0},
  {0,0,1,0},{0,0,1,1},{0,0,0,1},{1,0,0,1}
};
unsigned long lastRead = 0, lastStep = 0;
bool stopped = false, energized = false;
int phase = 7;
// EEPROM: firma + extremo confirmado. 2 significa movimiento/interrupción.
const byte EEPROM_TAG = 0xB6;
void remember(byte endpoint) {
  EEPROM.update(1, 2); // Primero invalidar, incluso ante pérdida de alimentación.
  EEPROM.update(0, EEPROM_TAG);
  EEPROM.update(1, endpoint);
}
void releaseMotor() {
  for (byte i=0; i<4; ++i) digitalWrite(MOTOR_PINS[i], LOW);
  energized = false;
}
void report() {
  Serial.print(F("STATE heater=")); Serial.print(!stopped && control.heater);
  Serial.print(F(" alarm=")); Serial.print(control.alarm || !door.known);
  Serial.print(F(" position=")); Serial.print(door.position);
  Serial.print(F(" target=")); Serial.print(door.target);
  Serial.print(F(" referenced=")); Serial.print(door.known);
  Serial.print(F(" stopped=")); Serial.println(stopped);
}
void setup() {
  digitalWrite(HEATER_PIN, !HEATER_ACTIVE); pinMode(HEATER_PIN, OUTPUT);
  digitalWrite(ALARM_PIN, !ALARM_ACTIVE); pinMode(ALARM_PIN, OUTPUT);
  for (byte i=0; i<4; ++i) {
    digitalWrite(MOTOR_PINS[i], LOW); pinMode(MOTOR_PINS[i], OUTPUT);
  }
  if (EEPROM.read(0) == EEPROM_TAG && EEPROM.read(1) <= 1)
    door.reference(EEPROM.read(1) == 1);
  Serial.begin(115200);
  Serial.println(F("READY BROODER_3"));
  Serial.println(F("S stop | A auto | O reference OPEN | C reference CLOSED | ? state"));
  // Dar al DHT11 tiempo para estabilizarse tras el encendido.
  lastRead = millis();
  report();
}
void handleCommand(char c) {
    if (c == 'S' || c == 's') {
      doorPolicy.reset();
      stopped = true; releaseMotor();
      digitalWrite(HEATER_PIN, !HEATER_ACTIVE);
      Serial.println(F("OK STOP"));
    } else if (c == 'A' || c == 'a') {
      stopped = false; Serial.println(F("OK AUTO"));
    } else if (c == 'O' || c == 'o' || c == 'C' || c == 'c') {
      if (energized) Serial.println(F("ERR STOP FIRST"));
      else {
        bool closed = c == 'C' || c == 'c';
        door.reference(closed); remember(closed ? 1 : 0);
        Serial.println(closed ? F("OK REFERENCE CLOSED") : F("OK REFERENCE OPEN"));
      }
    } else if (c == '?') report();
}
char commandLine[8];
byte commandLength = 0;
bool commandOverflow = false;
void loop() {
  if (Serial.available()) {
    char input = Serial.read();
    if (input == '\n') {
      commandLine[commandLength] = 0;
      char command = commandOverflow ? 0 : decodeCommand(commandLine);
      if (command) handleCommand(command);
      else Serial.println(F("ERR FRAME"));
      commandLength = 0; commandOverflow = false;
    } else if (input != '\r') {
      if (commandLength < sizeof(commandLine)-1) commandLine[commandLength++] = input;
      else commandOverflow = true;
    }
  }
  unsigned long now = millis();
  if (now - lastRead >= 2500UL) {
    lastRead = now;
    int humidity=0, temperature=0;
    bool valid = sensor.read(humidity, temperature);
    control.sample(temperature, valid, millis());
    if (valid) {
      Serial.print(F("TEMP ")); Serial.print(temperature);
      Serial.print(F(" HUM ")); Serial.println(humidity);
      if (!stopped) {
        DoorAction action = doorPolicy.sample(temperature, true, millis());
        if (action == DoorAction::Close) door.request(true);
        else if (action == DoorAction::Open) door.request(false);
      }
    } else {
      doorPolicy.reset();
      Serial.println(F("FAULT DHT11"));
    }
    report();
  }
  control.tick(millis());
  bool fault = control.climate == Climate::Fault;
  if (fault) doorPolicy.reset();
  digitalWrite(HEATER_PIN, !stopped && control.heater ? HEATER_ACTIVE : !HEATER_ACTIVE);
  digitalWrite(ALARM_PIN, control.alarm || !door.known ? ALARM_ACTIVE : !ALARM_ACTIVE);
  if (stopped || fault || !door.moving()) {
    if (energized) releaseMotor();
    return;
  }
  if (!energized) {
    remember(2);
    energized = true;
    lastStep = micros();
    Serial.println(door.target ? F("DOOR CLOSING") : F("DOOR OPENING"));
  }
  unsigned long us = micros();
  if (us - lastStep >= STEP_INTERVAL_US) {
    lastStep = us;
    phase = (phase + door.step() * CLOSE_DIRECTION + 8) % 8;
    for (byte i=0; i<4; ++i) digitalWrite(MOTOR_PINS[i], PATTERN[phase][i]);
    if (!door.moving()) {
      releaseMotor(); remember(door.position == Door::TRAVEL ? 1 : 0);
      Serial.println(F("OK DOOR DONE"));
    }
  }
}
