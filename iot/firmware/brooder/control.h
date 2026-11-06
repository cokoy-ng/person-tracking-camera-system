#pragma once
#include <stdint.h>
#include "cycles.h"

enum class Climate { Fault, Cold, Normal, Hot };

// Un margen alrededor del centro y permanencia minima evitan conmutacion rapida.
class RelayDemand {
 public:
  bool on = false;
  void reset() { on = false; initialized = false; }
  bool update(bool request, bool hardOff, uint32_t now, uint32_t dwell, bool hardOn = false) {
    if (hardOff) {
      if (on || !initialized) { changedAt = now; initialized = true; }
      on = false;
    } else if (hardOn) {
      if (!on || !initialized) { changedAt = now; initialized = true; }
      on = true;
    } else if (!initialized || (request != on && uint32_t(now-changedAt) >= dwell)) {
      on = request; changedAt = now; initialized = true;
    }
    return on;
  }
 private:
  bool initialized = false;
  uint32_t changedAt = 0;
};

class ClimateControl {
 public:
  Climate climate = Climate::Fault;
  bool heater = false, humidifier = false, ventilation = false, humidityAlarm = false;
  // 1 calor, 2 HR alta, 4 HR baja, 8 renovacion bloqueada por frio.
  uint8_t airReasons = 0;
  uint8_t reasons = 16; // temp baja/alta, HR baja/alta, sensor, puerta.
  void sample(float temperature, float humidity, uint8_t cycle, bool valid, uint32_t now) {
    if (!valid || cycle < 1 || cycle > 4 ||
        !(temperature >= 0 && temperature <= 50) || !(humidity >= 0 && humidity <= 100)) {
      fault(); return;
    }
    if (cycle != previousCycle) {
      heat.reset(); ventilate.reset();
      coolingDemand = dryingDemand = false;
    }
    previousCycle = cycle;
    const CycleProfile& p = CYCLES[cycle-1];
    seen = true; lastSample = now;
    climate = temperature < p.minTemp ? Climate::Cold :
              temperature > p.maxTemp ? Climate::Hot : Climate::Normal;
    reasons = (temperature < p.minTemp ? 1 : temperature > p.maxTemp ? 2 : 0) |
              (humidity < p.minHumidity ? 4 : humidity > p.maxHumidity ? 8 : 0);
    humidityAlarm = (reasons & 12) != 0;
    bool wantHeat = heat.on;
    if (temperature <= p.maxTemp-1.0f) wantHeat = true;
    else if (temperature >= p.maxTemp) wantHeat = false;
    // Dentro de rango: espera60s entre conmutaciones; por debajo del minimo
    // recupera calor inmediatamente. El maximo siempre corta sin esperar.
    heater = heat.update(wantHeat, temperature >= p.maxTemp, now, 60000UL, temperature <= p.minTemp);
    const float centerH = (p.minHumidity+p.maxHumidity) / 2.0f;
    if (temperature >= p.maxTemp) coolingDemand = true;
    else if (temperature <= p.maxTemp-1.0f) coolingDemand = false;
    if (humidity >= centerH+2.0f) dryingDemand = true;
    else if (humidity <= centerH) dryingDemand = false;
    bool tooCold = temperature <= p.minTemp;
    bool ventRequest = coolingDemand || dryingDemand;
    bool ventMaximum = temperature >= p.maxTemp || humidity >= p.maxHumidity;
    ventilation = ventilate.update(ventRequest, tooCold, now, 15000UL, ventMaximum);
    humidifier = false; // D7 es motobomba exclusivamente manual.
    airReasons = (coolingDemand ? 1 : 0) | (dryingDemand ? 2 : 0) |
                 (tooCold && ventRequest ? 8 : 0);

  }
  void tick(uint32_t now) {
    if (!seen || uint32_t(now-lastSample) >= 6000UL) fault();
  }
 private:
  RelayDemand heat, ventilate;
  bool coolingDemand = false, dryingDemand = false;
  bool seen = false;
  uint8_t previousCycle = 0;
  uint32_t lastSample = 0;
  void fault() {
    seen = false; previousCycle = 0; climate = Climate::Fault;
    heat.reset(); ventilate.reset();
    coolingDemand = dryingDemand = false;
    heater = humidifier = ventilation = humidityAlarm = false;
    airReasons = 0; reasons = 16;
  }
};
