#pragma once
#include <stdint.h>
// Orden: calefaccion, humedad, extraccion, entrada, alarma.
class ManualOutputs {
 public:
  uint8_t modes[5] = {0,0,0,0,0}; // 0 automatico, 1 apagado, 2 encendido.
  uint32_t changed[5] = {0,0,0,0,0};
  uint32_t duration[5] = {0,0,0,0,0};
  void set(uint8_t index, uint8_t mode, uint32_t now, uint32_t durationMs=60000UL) {
    if(index < 5 && mode < 3) { modes[index]=mode; changed[index]=now; duration[index]=durationMs; }
  }
  void tick(uint32_t now) {
    for(uint8_t i=0;i<5;++i) if(modes[i] && duration[i] && uint32_t(now-changed[i])>=duration[i]) modes[i]=0;
  }
  uint32_t remaining(uint8_t i, uint32_t now) const {
    if(!modes[i] || !duration[i]) return 0;
    uint32_t elapsed=now-changed[i];
    return elapsed>=duration[i] ? 0 : (duration[i]-elapsed+999)/1000;
  }
  bool output(uint8_t i, bool automatic, bool blocked) const {
    return !blocked && (modes[i]==0 ? automatic : modes[i]==2);
  }
};
