#pragma once
#include <stdint.h>

// Señal D3. Temporizador de presencia: la cámara (LIGHT PERSON) y el gesto
// de sonido (ver sound_sensor.h) comparten el mismo temporizador de apagado.
// Unsigned subtraction also handles the millis() counter wrapping.
class LightControl {
 public:
  uint32_t holdMs = 30000;
  uint32_t lastTrigger = 0;
  bool on = false;
  bool cameraSeen = false;
  uint32_t lastCamera = 0;
  void trigger(uint32_t now) { lastTrigger = now; on = true; }
  void person(uint32_t now) { cameraSeen = true; lastCamera = now; trigger(now); }
  void soundOff(uint32_t now) {
    // Camera sends presence every 500ms. A live person has priority.
    if (!cameraSeen || uint32_t(now - lastCamera) >= 1500) on = false;
  }
  void update(uint32_t now) {
    if (cameraSeen && uint32_t(now - lastCamera) >= 1500) cameraSeen = false;
    if (on && uint32_t(now - lastTrigger) >= holdMs) on = false;
  }
};
