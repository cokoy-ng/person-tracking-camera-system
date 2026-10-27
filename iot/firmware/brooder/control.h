#pragma once
#include <stdint.h>

// Umbrales solicitados por el usuario; no son una recomendación de crianza.
enum class Climate { Fault, Cold, Normal, Hot };

class ClimateControl {
 public:
  Climate climate = Climate::Fault;
  bool heater = false;
  bool alarm = true;

  void sample(float celsius, bool valid, uint32_t now) {
    // Rechaza NaN, infinito y valores fuera del rango de esta aplicación.
    if (!valid || !(celsius >= -20.0f && celsius <= 80.0f)) {
      fault();
      return;
    }
    seen = true;
    lastSample = now;
    climate = celsius < 26.0f ? Climate::Cold :
              celsius > 32.0f ? Climate::Hot : Climate::Normal;
    // Histéresis: encender debajo de 26, apagar a partir de 30.
    if (celsius < 26.0f) heater = true;
    else if (celsius >= 30.0f) heater = false;
    alarm = climate != Climate::Normal;
  }

  void tick(uint32_t now) {
    if (!seen || uint32_t(now - lastSample) >= 6000UL) fault();
  }

 private:
  bool seen = false;
  uint32_t lastSample = 0;
  void fault() {
    seen = false;
    climate = Climate::Fault;
    heater = false;
    alarm = true;
  }
};
