#pragma once
class Servo {
 public:
  bool active = false;
  int us = 0;
  bool attached() { return active; }
  void attach(int, int, int) { active = true; }
  void detach() { active = false; }
  void writeMicroseconds(int value) { us = value; }
};
