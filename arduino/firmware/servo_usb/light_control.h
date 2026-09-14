#pragma once
#include <stdint.h>

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

class SoundGesture {
 public:
  bool previousActive = false;
  bool heard = false;
  uint32_t lastSound = 0;
  uint32_t events = 0;
  uint32_t triples = 0;
  uint8_t count = 0;
  void reset(bool active) {
    previousActive = active;
    heard = false;
    count = 0;
  }
  // One onset per pulse; reject chatter/echo inside 180ms.
  // Three onsets separated by 180..900ms form the OFF gesture.
  int update(bool active, uint32_t now) {
    bool onset = active && !previousActive;
    previousActive = active;
    if (!onset || (heard && uint32_t(now - lastSound) < 180)) return 0;
    if (!heard || uint32_t(now - lastSound) > 900) count = 0;
    heard = true;
    lastSound = now;
    ++events;
    if (++count == 3) {
      count = 0;
      ++triples;
      return -1;
    }
    return 1;
  }
};
