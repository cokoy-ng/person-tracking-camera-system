#pragma once
#include <stdint.h>

// Señal D4. Reconoce palmadas para encender/apagar la luz por gesto,
// independiente de la cámara (ver relay_light.h).
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
