#pragma once
class Servo {
 public:
  bool attached = false;
  int angle = -1;
  void attach(int pin) { assert(pin == 6); attached=true; }
  void detach() { attached=false; }
  void write(int value) { assert(value>=0 && value<=180); angle=value; }
};
