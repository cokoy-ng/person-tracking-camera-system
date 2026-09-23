#pragma once
class Servo {
  bool enabled = false;
 public:
  bool attached() { return enabled; }
  void attach(int) { enabled = true; }
  void detach() { enabled = false; }
  void write(int) {}
};
