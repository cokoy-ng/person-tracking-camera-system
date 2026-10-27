#pragma once
#include <stdint.h>
enum class DoorAction { Hold, Close, Open };
class DoorPolicy {
 public:
  void reset() { hot = false; }
  DoorAction sample(float temperature, bool valid, uint32_t now) {
    if (!valid || !(temperature >= -20 && temperature <= 80)) {
      reset();
      return DoorAction::Hold;
    }
    if (temperature <= 32) {
      reset();
      return DoorAction::Close;
    }
    if (!hot) { hot = true; hotSince = now; }
    return uint32_t(now - hotSince) > 300000UL ? DoorAction::Open : DoorAction::Hold;
  }
 private:
  bool hot = false;
  uint32_t hotSince = 0;
};
class Door {
 public:
  static const int32_t TRAVEL = 49152L; // 12 * 4096 medios pasos.
  int32_t position = 0;
  int32_t target = 0;
  bool known = false;
  void reference(bool closed) {
    position = target = closed ? TRAVEL : 0;
    known = true;
  }
  void request(bool closed) { if (known) target = closed ? TRAVEL : 0; }
  bool moving() const { return known && position != target; }
  int step() {
    if (!moving()) return 0;
    int direction = target > position ? 1 : -1;
    position += direction;
    return direction;
  }
};
