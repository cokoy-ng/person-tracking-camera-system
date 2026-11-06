#include <cassert>
#include <iostream>
void applyOutputs();
#include "../firmware/brooder/brooder.ino"
int main() {
  setup();
  assert(!stopped && DOOR_ENABLED && !DOOR_AUTO_ENABLED);
  assert(HEATER_PIN==9 && HUMIDIFIER_FAN_PIN==7 && EXHAUST_FAN_PIN==8);
  assert(SERVO_PIN==6);
  for(int i=0;i<4;++i) assert(MOTOR_PINS[i]==10+i);
  assert(!touched[6]);
  for(int pin=A1;pin<=A5;++pin) assert(!touched[pin]);
  // Manual output cannot bypass sensor fault.
  for(int i=0;i<5;++i) if(i!=1) manual.set(i,2,millis());
  applyOutputs();
  assert(levels[9]==!HEATER_ACTIVE && levels[7] && levels[8]);
  stopped=false;
  control.sample(25,55,4,true,millis());
  heatLimit=humidityLimit=coldLimit=false;
  setManualOutput(1,2,millis());
  applyOutputs();
  assert(levels[9]==HEATER_ACTIVE && !levels[7] && !levels[8] && levels[A0]);
  assert(!outputState[3]);
  heatLimit=true; applyOutputs(); assert(levels[9]==!HEATER_ACTIVE);
  humidityLimit=true; applyOutputs(); assert(!levels[7]); // Manual pump ignores climate HR.
  coldLimit=true; applyOutputs(); assert(levels[8]);
  // An explicit manual ON works during automatic pause, without resuming others.
  handleCommand('S');
  control.sample(25,55,4,true,millis());
  heatLimit=humidityLimit=coldLimit=false;
  for(int i=0;i<3;++i) setManualOutput(i,0,millis());
  setManualOutput(1,2,millis(),1000); applyOutputs();
  assert(stopped && !levels[7] && levels[8] && levels[9]==!HEATER_ACTIVE);
  handleCommand('S'); applyOutputs(); assert(levels[7]);
  setManualOutput(1,2,millis(),1000); applyOutputs(); assert(!levels[7]);
  mockTime+=1000; applyOutputs(); assert(levels[7]);
  setManualOutput(0,2,millis()); heatLimit=true; applyOutputs(); assert(levels[9]==!HEATER_ACTIVE && outputBlock[0]==3);
  handleCommand('S');
  handleCommand('2');
  assert(activeCycle==0 && levels[9]==!HEATER_ACTIVE && levels[7] && levels[8]);
  // No sensor response: no control cycle, including after two full polling passes.
  mockTime+=2500; loop(); mockTime+=2500; loop();
  assert(activeCycle==0 && levels[9]==!HEATER_ACTIVE && levels[7] && levels[8]);
  for(int pin=A1;pin<=A5;++pin) assert(!touched[pin]);
  assert(!touched[6]);
  for(int pin=10;pin<=13;++pin) assert(!levels[pin]);
  handleCommand('Z');
  assert(servoStage==1 && auxiliaryServo.attached && auxiliaryServo.angle==180);
  mockTime+=9999; tickServo(); assert(servoStage==1);
  mockTime+=1; tickServo(); assert(servoStage==2 && auxiliaryServo.angle==180);
  mockTime+=2999; tickServo(); assert(servoStage==2);
  mockTime+=1; tickServo(); assert(servoStage==3 && auxiliaryServo.angle==130);
  mockTime+=8999; tickServo(); assert(servoStage==3 && auxiliaryServo.attached);
  mockTime+=1; tickServo(); assert(!servoStage && !auxiliaryServo.attached);
  for(int stage=1;stage<=3;++stage) {
    handleCommand('Z');
    if(stage>=2) { mockTime+=10000; tickServo(); }
    if(stage>=3) { mockTime+=3000; tickServo(); }
    handleCommand('S'); assert(!servoStage && !auxiliaryServo.attached);
  }
  mockTime=0xfffffff0UL; handleCommand('Z');
  mockTime+=10000; tickServo(); assert(servoStage==2);
  handleCommand('S');
  assert(levels[7]==HIGH && levels[8]==HIGH && levels[9]==!HEATER_ACTIVE);
  // Confirmed cable changes restore climate modes, never undo an explicit STOP.
  handleCommand('S');
  for(int i=0;i<3;++i) setManualOutput(i,1,millis());
  adoptClimateCycle(1); assert(stopped && lastConfirmedCycle==1);
  for(int i=0;i<3;++i) if(i!=1) assert(manual.modes[i]==0 && !manualPauseOverride[i]);
  assert(manual.modes[1]==1);
  setManualOutput(1,1,millis());
  adoptClimateCycle(0); adoptClimateCycle(1); assert(manual.modes[1]==1);
  adoptClimateCycle(2); assert(manual.modes[1]==1 && stopped);
  setManualOutput(0,1,millis()); handleCommand('A');
  assert(!stopped && manual.modes[0]==0);
  handleCommand('S');
  // No automatic condition can start the pump, even at extremely low HR.
  handleCommand('A');
  for(byte cycle=1;cycle<=4;++cycle) {
    adoptClimateCycle(cycle);
    control.sample(30,1,cycle,true,millis());
    applyOutputs(); assert(!outputState[1] && levels[7]==HIGH);
  }
  // Explicit ON is independent of sensor and humidity; timer, OFF and STOP cut it.
  control.sample(0,0,0,false,millis());
  setManualOutput(1,2,millis(),1000); applyOutputs();
  assert(outputState[1] && levels[7]==LOW);
  adoptClimateCycle(1); applyOutputs(); assert(outputState[1]);
  mockTime+=1000; applyOutputs(); assert(!outputState[1] && manual.modes[1]==1);
  setManualOutput(1,2,millis(),0); applyOutputs(); assert(outputState[1]);
  handleCommand('S'); applyOutputs(); assert(!outputState[1] && manual.modes[1]==1);
  handleCommand('A'); applyOutputs(); assert(!outputState[1]);
  handleCommand('S');
  // Door rejects motion before a real endpoint reference; no automatic movement.
  handleCommand('D'); assert(!doorRunRequested && !door.known);
  handleCommand('O'); assert(door.known && door.position==0 && !doorRunRequested);
  handleCommand('D'); assert(doorRunRequested && door.target==Door::TRAVEL && stopped);
  handleCommand('B'); assert(doorRunRequested && door.target==Door::TRAVEL); // busy
  for(int i=0;i<3000;++i) loop();
  assert(door.position>0 && doorRunRequested);
  handleCommand('X'); assert(!doorRunRequested && !energized);
  auto pausedPosition=door.position;
  for(int i=0;i<3000;++i) loop();
  assert(door.position==pausedPosition);
  handleCommand('B'); assert(doorRunRequested && door.target==0);
  handleCommand('S'); assert(!doorRunRequested && !energized);
  assert(decodeCommand("1")=='1' && decodeCommand("~434")=='4');
  std::cout << "OK: new wiring, sensor selection D2-D5, untouched A1-A5/D6, automatic startup, faults and manual limits\n";
}
