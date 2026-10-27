#pragma once
#include <string.h>

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
  return c && strchr("SsAaOoCc?", c) ? c : 0;
}
