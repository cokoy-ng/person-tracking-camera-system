#pragma once
#include <stdint.h>
// Fuera de rango 30 s; fallo de sensor/posicion 10 s. Recuperacion 15 s.
// Solo emite pulsos si la condicion sigue presente: 1 s cada 60 s.
class AlarmPolicy {
 public:
  bool active = false, pending = false, recovering = false, sounding = false;
  uint8_t reasons = 0;
  void reset() {
    active = pending = recovering = sounding = false;
    reasons = pendingKind = 0;
  }
  void update(uint8_t current, uint32_t now) {
    if (current) {
      recovering = false; reasons = current;
      if (!active) {
        uint8_t kind = current & 48 ? 2 : 1;
        if (!pending || kind != pendingKind) {
          pending = true; pendingKind = kind; pendingAt = now;
        }
        if (uint32_t(now-pendingAt) >= (kind == 2 ? 10000UL : 30000UL)) {
          active = true; pending = false; alarmAt = now;
        }
      }
    } else {
      pending = false;
      if (active) {
        if (!recovering) { recovering = true; recoveryAt = now; }
        if (uint32_t(now-recoveryAt) >= 15000UL) reset();
      } else reasons = 0;
    }
    sounding = active && current && uint32_t(now-alarmAt) % 60000UL < 1000UL;
  }
 private:
  uint8_t pendingKind = 0;
  uint32_t pendingAt = 0, recoveryAt = 0, alarmAt = 0;
};
