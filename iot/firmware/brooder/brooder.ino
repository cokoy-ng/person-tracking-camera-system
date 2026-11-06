#include <Arduino.h>
#include <EEPROM.h>
#include <Servo.h>
#include "config.h"
#include "control.h"
#include "alarm_policy.h"
#include "door.h"
#include "protocol.h"
#include "dht11_sensor.h"
#include "manual_outputs.h"
Servo auxiliaryServo;
byte servoStage = 0;
int servoAngle = -1;
unsigned long servoSince = 0;
void stopServo() {
  auxiliaryServo.detach();
  servoStage = 0;
}
void tickServo() {
  if (!servoStage) return;
  unsigned long elapsed = millis() - servoSince;
  if (servoStage == 1 && elapsed >= 10000UL) {
    servoStage = 2; servoSince = millis();
    Serial.println(F("SERVO WAIT 180"));
  } else if (servoStage == 2 && elapsed >= 3000UL) {
    auxiliaryServo.write(130); servoAngle = 130; servoStage = 3; servoSince = millis();
    Serial.println(F("SERVO ANGLE 130"));
  } else if (servoStage == 3 && elapsed >= 9000UL) {
    stopServo(); Serial.println(F("OK SERVO DONE"));
  }
}
ManualOutputs manual;
bool manualPauseOverride[3] = {false,false,false};
byte outputBlock[3] = {0,0,0};
void setManualOutput(byte index, byte mode, unsigned long now, unsigned long duration=60000UL) {
  if (index==1 && mode==0) mode=1;
  manual.set(index, mode, now, duration);
  if (index<3) manualPauseOverride[index] = mode==2;
}
bool outputState[5] = {false,false,false,false,false};
bool heatLimit = true, humidityLimit = true, coldLimit = true;
ClimateControl control;
AlarmPolicy alarmPolicy;
Door door;
DoorPolicy doorPolicy;
bool doorRunRequested = false;
DHT11Sensor sensors[] = {DHT11Sensor(2), DHT11Sensor(3), DHT11Sensor(4), DHT11Sensor(5)};
CycleSelector cycleSelector;
byte activeCycle = 0;
byte lastConfirmedCycle = 0;
void adoptClimateCycle(byte selected) {
  if (!selected || selected>4 || selected==lastConfirmedCycle) return;
  lastConfirmedCycle=selected;
  for(byte i=0;i<3;++i) {
    if(i==1) continue;
    manual.set(i,0,millis(),0);
    manualPauseOverride[i]=false;
  }
  Serial.print(F("AUTO CYCLE ")); Serial.println(selected);
}
const byte PATTERN[8][4] = {
  {1,0,0,0},{1,1,0,0},{0,1,0,0},{0,1,1,0},
  {0,0,1,0},{0,0,1,1},{0,0,0,1},{1,0,0,1}
};
unsigned long lastRead = 0, lastStep = 0;
bool stopped = false, energized = false; // Automatico; sin sensor/ciclo valido las cargas permanecen apagadas.
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
void updateAlarm() {
  alarmPolicy.update(control.reasons | (DOOR_ENABLED && DOOR_AUTO_ENABLED && !door.known ? 32 : 0), millis());
}
void report() {
  Serial.println(F("FIRMWARE BROODER_16_MANUAL_PUMP"));
  Serial.println(F("CYCLE_SELECTION hardware=1"));
  unsigned long servoRemaining = 0;
  if (servoStage) {
    unsigned long duration = servoStage == 1 ? 22000UL : servoStage == 2 ? 12000UL : 9000UL;
    unsigned long elapsed = millis() - servoSince;
    servoRemaining = elapsed < duration ? (duration-elapsed+999)/1000 : 0;
  }
  Serial.print(F("SERVO stage=")); Serial.print(servoStage);
  Serial.print(F(" angle=")); Serial.print(servoAngle);
  Serial.print(F(" remaining=")); Serial.println(servoRemaining);
  Serial.print(F("DOOR_CONTROL running=")); Serial.print(doorRunRequested ? 1 : 0);
  Serial.println(F(" manual_only=1"));
  Serial.print(F("BLOCK codes="));
  for(byte i=0;i<3;++i) { if(i) Serial.print(','); Serial.print(outputBlock[i]); }
  Serial.println();
  Serial.print(F("CONTROL modes="));
  for(byte i=0;i<5;++i) Serial.print(manual.modes[i]);
  Serial.print(F(" outputs="));
  for(byte i=0;i<5;++i) Serial.print(outputState[i] ? 1 : 0);
  Serial.print(F(" door_enabled=")); Serial.print(DOOR_ENABLED ? 1 : 0);
  Serial.print(F(" remaining="));
  for(byte i=0;i<5;++i) { if(i) Serial.print(','); Serial.print(manual.remaining(i,millis())); }
  Serial.println();
  Serial.print(F("ALERT active=")); Serial.print(alarmPolicy.active);
  Serial.print(F(" pending=")); Serial.print(alarmPolicy.pending);
  Serial.print(F(" recovering=")); Serial.print(alarmPolicy.recovering);
  Serial.print(F(" sounding=")); Serial.print(alarmPolicy.sounding);
  Serial.print(F(" reasons=")); Serial.println(alarmPolicy.reasons);
  Serial.print(F("CYCLE id=")); Serial.print(activeCycle);
  Serial.print(F(" pin=")); Serial.print(activeCycle ? CYCLES[activeCycle-1].pin : 0);
  Serial.print(F(" humidifier=")); Serial.print(outputState[1]);
  Serial.print(F(" exhaust=")); Serial.print(outputState[2]);
  Serial.print(F(" intake=")); Serial.print(outputState[3]);
  Serial.print(F(" reason=")); Serial.println(control.airReasons);
  Serial.print(F("STATE heater=")); Serial.print(outputState[0]);
  Serial.print(F(" alarm=")); Serial.print(alarmPolicy.active);
  Serial.print(F(" position=")); Serial.print(door.position);
  Serial.print(F(" target=")); Serial.print(door.target);
  Serial.print(F(" referenced=")); Serial.print(door.known);
  Serial.print(F(" stopped=")); Serial.println(stopped);
}
void setup() {
  manual.set(1,1,millis(),0); // Bomba apagada al arrancar.
  digitalWrite(HUMIDIFIER_FAN_PIN, !FAN_ACTIVE); pinMode(HUMIDIFIER_FAN_PIN, OUTPUT);
  digitalWrite(EXHAUST_FAN_PIN, !FAN_ACTIVE); pinMode(EXHAUST_FAN_PIN, OUTPUT);
  for(byte i=0;i<4;++i) pinMode(CYCLES[i].pin, INPUT_PULLUP);
  digitalWrite(HEATER_PIN, !HEATER_ACTIVE); pinMode(HEATER_PIN, OUTPUT);
  digitalWrite(ALARM_PIN, !ALARM_ACTIVE); pinMode(ALARM_PIN, OUTPUT);
  for (byte i=0; i<4; ++i) {
    digitalWrite(MOTOR_PINS[i], LOW); pinMode(MOTOR_PINS[i], OUTPUT);
  }
  if (EEPROM.read(0) == EEPROM_TAG && EEPROM.read(1) <= 1)
    door.reference(EEPROM.read(1) == 1);
  Serial.begin(115200);
  Serial.println(F("READY BROODER_16_MANUAL_PUMP"));
  Serial.println(F("S stop | A auto | sensor D2-D5 selects cycle | O/C reference | ? state"));
  // Dar al DHT11 tiempo para estabilizarse tras el encendido.
  lastRead = millis();
  report();
}
void handleCommand(char c) {
    if (c == 'B' || c == 'D') {
      if (!door.known) { Serial.println(F("ERR DOOR REFERENCE REQUIRED")); return; }
      if (doorRunRequested || energized) { Serial.println(F("ERR DOOR BUSY")); return; }
      door.request(c == 'D');
      doorRunRequested = door.moving();
      Serial.println(c == 'D' ? F("OK DOOR CLOSE") : F("OK DOOR OPEN"));
      report(); return;
    }
    if (c == 'X') {
      doorRunRequested = false; releaseMotor();
      Serial.println(F("OK DOOR STOP")); report(); return;
    }
    if (c == 'Z') {
      if (servoStage) { Serial.println(F("ERR SERVO BUSY")); return; }
      auxiliaryServo.attach(SERVO_PIN);
      auxiliaryServo.write(180); servoAngle = 180;
      servoStage = 1; servoSince = millis();
      Serial.println(F("OK SERVO TEST"));
      Serial.println(F("SERVO ANGLE 180"));
      return;
    }
    if (c >= '1' && c <= '4') {
      Serial.println(F("ERR CYCLE SELECT BY SENSOR D2-D5")); return;
    }
    const char* commands = "FGHIJKLMNPQRTUV";
    const char* found = c ? strchr(commands,c) : 0;
    if(found) {
      byte action = found-commands;
      if (action/3 == 3) { Serial.println(F("ERR OUTPUT REMOVED")); return; }
      if (action/3==1 && action%3==0) { Serial.println(F("ERR PUMP MANUAL ONLY")); return; }
      setManualOutput(action/3,action%3,millis());
      applyOutputs();
      Serial.print(F("OK MANUAL ")); Serial.println(c);
      report();
      return;
    }
    if (c == 'S' || c == 's') {
      doorPolicy.reset();
      stopped = true; doorRunRequested = false; releaseMotor(); stopServo();
      for(byte i=0;i<3;++i) manualPauseOverride[i]=false;
      manual.set(1,1,millis(),0);
      digitalWrite(HEATER_PIN, !HEATER_ACTIVE);
      digitalWrite(HUMIDIFIER_FAN_PIN, !FAN_ACTIVE);
      digitalWrite(EXHAUST_FAN_PIN, !FAN_ACTIVE);
      Serial.println(F("OK STOP"));
    } else if (c == 'A' || c == 'a') {
      stopped = false;
      for(byte i=0;i<3;++i) { if(i==1) continue; manual.set(i,0,millis(),0); manualPauseOverride[i]=false; }
      applyOutputs();
      Serial.println(F("OK AUTO"));
    } else if (c == 'O' || c == 'o' || c == 'C' || c == 'c') {
      if (energized || doorRunRequested) Serial.println(F("ERR STOP FIRST"));
      else {
        bool closed = c == 'C' || c == 'c';
        door.reference(closed); remember(closed ? 1 : 0);
        Serial.println(closed ? F("OK REFERENCE CLOSED") : F("OK REFERENCE OPEN"));
      }
    } else if (c == '?') report();
}
char commandLine[20];
byte commandLength = 0;
bool commandOverflow = false;
void loop() {
  tickServo();
  if (Serial.available()) {
    char input = Serial.read();
    if (input == '\n') {
      commandLine[commandLength] = 0;
      uint8_t index, mode; uint32_t seconds;
      if(!commandOverflow && decodeManual(commandLine,index,mode,seconds)) {
        if (index == 3) {
          Serial.println(F("ERR OUTPUT REMOVED"));
          commandLength=0; commandOverflow=false; return;
        }
        if (index==1 && mode==0) {
          Serial.println(F("ERR PUMP MANUAL ONLY"));
          commandLength=0; commandOverflow=false; return;
        }
        setManualOutput(index,mode,millis(),seconds*1000UL);
        applyOutputs();
        Serial.print(F("OK CONTROL ")); Serial.println(commandLine);
        report();
        commandLength=0; commandOverflow=false;
        return;
      }
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
    byte mask = 0;
    for(byte i=0;i<4;++i) {
      int h=0,t=0;
      if(sensors[i].read(h,t)) { mask |= 1 << i; humidity=h; temperature=t; }
    }
    byte selected = cycleSelector.select(mask);
    Serial.print(F("SENSOR"));
    for(byte i=0;i<4;++i) {
      Serial.print(F(" D")); Serial.print(i+2); Serial.print('='); Serial.print(sensors[i].diagnostic);
    }
    Serial.print(F(" mask=")); Serial.println(mask);
    if (selected != activeCycle) {
      doorPolicy.reset();
      if (selected) alarmPolicy.reset();
    }
    adoptClimateCycle(selected);
    activeCycle = selected;
    bool valid = activeCycle != 0;
    heatLimit = !valid || temperature >= CYCLES[activeCycle-1].maxTemp;
    humidityLimit = !valid || humidity >= CYCLES[activeCycle-1].maxHumidity;
    coldLimit = !valid || temperature <= CYCLES[activeCycle-1].minTemp;
    control.sample(temperature, humidity, activeCycle, valid, millis());
    if (valid) {
      Serial.print(F("TEMP ")); Serial.print(temperature);
      Serial.print(F(" HUM ")); Serial.println(humidity);
      if (!stopped && DOOR_ENABLED && DOOR_AUTO_ENABLED) {
        DoorAction action = doorPolicy.sample(temperature, true, millis(), CYCLES[activeCycle-1].maxTemp);
        if (action == DoorAction::Close) door.request(true);
        else if (action == DoorAction::Open) door.request(false);
      }
    } else {
      doorPolicy.reset();
      Serial.println(F("FAULT DHT11 CYCLE: use one sensor on D2-D5"));
    }
    updateAlarm();
    applyOutputs();
    report();
  }
  control.tick(millis());
  updateAlarm();
  bool fault = control.climate == Climate::Fault;
  if (fault) doorPolicy.reset();
  applyOutputs();
  if (!DOOR_ENABLED || !doorRunRequested || !door.moving()) {
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
      doorRunRequested = false;
      releaseMotor(); remember(door.position == Door::TRAVEL ? 1 : 0);
      Serial.println(F("OK DOOR DONE"));
    }
  }
}
void applyOutputs() {
  manual.tick(millis());
  if(manual.modes[1]==0) manual.set(1,1,millis(),0); // Fin de temporizador: OFF, nunca automatico.
  bool fault = control.climate == Climate::Fault;
  bool limits[3] = {heatLimit,false,coldLimit};
  bool automatic[3] = {control.heater,false,control.ventilation};
  for(byte i=0;i<3;++i) {
    bool paused = stopped && !(manual.modes[i]==2 && manualPauseOverride[i]);
    outputBlock[i] = fault && i!=1 ? 2 : limits[i] ? i+3 : paused ? 1 : 0;
    outputState[i] = manual.output(i,automatic[i],outputBlock[i]!=0);
  }
  outputState[3] = false; // Segunda salida retirada; A2-A5 no se escriben.
  outputState[4] = manual.output(4,alarmPolicy.sounding,false);
  digitalWrite(HEATER_PIN,outputState[0] ? HEATER_ACTIVE : !HEATER_ACTIVE);
  digitalWrite(HUMIDIFIER_FAN_PIN,outputState[1] ? FAN_ACTIVE : !FAN_ACTIVE);
  digitalWrite(EXHAUST_FAN_PIN,outputState[2] ? FAN_ACTIVE : !FAN_ACTIVE);
  digitalWrite(ALARM_PIN,outputState[4] ? ALARM_ACTIVE : !ALARM_ACTIVE);
}
