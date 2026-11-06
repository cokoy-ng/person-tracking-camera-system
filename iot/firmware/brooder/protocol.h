#pragma once
#include <string.h>
#include <stdint.h>

inline int hexDigit(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}
inline char decodeCommand(const char *line) {
  unsigned int length = strlen(line);
  // Monitor serie: una letra y salto de línea. Scripts: trama con checksum.
  char c = 0;
  if (length == 1) c = line[0];
  else if (length == 4 && line[0] == '~') {
    int hi = hexDigit(line[2]), lo = hexDigit(line[3]);
    if (hi < 0 || lo < 0 || (hi * 16 + lo) != int(line[1])) return 0;
    c = line[1];
  }
  return c && strchr("SsAaOoCc?ZBDX1234FGHIJKLMNPQRTUV", c) ? c : 0;
}

// !<salida><modo><segundos>*<XOR hexadecimal>, duracion0 = hasta volver a AUTO.
inline bool decodeManual(const char* line, uint8_t &index, uint8_t &mode, uint32_t &seconds) {
  unsigned int length=strlen(line);
  if(length<7 || length>11 || line[0]!='!' || line[1]<'0' || line[1]>'4' || line[2]<'0' || line[2]>'2' || line[length-3]!='*') return false;
  uint8_t checksum=0;
  for(unsigned int i=0;i<length-3;++i) checksum ^= uint8_t(line[i]);
  int hi=hexDigit(line[length-2]), lo=hexDigit(line[length-1]);
  if(hi<0 || lo<0 || checksum!=(hi*16+lo)) return false;
  seconds=0;
  for(unsigned int i=3;i<length-3;++i) {
    if(line[i]<'0' || line[i]>'9') return false;
    seconds=seconds*10+line[i]-'0';
  }
  if(seconds>86400UL) return false;
  index=line[1]-'0'; mode=line[2]-'0';
  return true;
}
