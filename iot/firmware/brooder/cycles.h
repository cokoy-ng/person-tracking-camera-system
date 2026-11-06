#pragma once
#include <stdint.h>
struct CycleProfile {
  uint8_t pin, firstDay, lastDay, minTemp, maxTemp, minHumidity, maxHumidity;
};
// Rangos del usuario. El pin selecciona la etapa, no mide edad.
static const CycleProfile CYCLES[] = {
  {2, 1, 3, 33, 34, 60, 70}, {3, 4, 7, 30, 32, 50, 65},
  {4, 8, 14, 27, 29, 50, 60}, {5, 15, 21, 24, 27, 50, 60}
};
class CycleSelector {
 public:
  uint8_t active = 0;
  uint8_t select(uint8_t mask) {
    uint8_t candidate = 0;
    for (uint8_t i=0; i<4; ++i) if (mask & (1 << i)) {
      if (candidate) { active = pending = 0; return 0; }
      candidate = i+1;
    }
    if (!candidate) { active = pending = 0; return 0; }
    // Dos lecturas validas consecutivas antes de controlar.
    active = pending == candidate ? candidate : 0;
    pending = candidate;
    return active;
  }
 private:
  uint8_t pending = 0;
};
enum class FanMode { Disabled, HumidityHigh, HumidityLow, TemperatureHigh, Ventilation };
