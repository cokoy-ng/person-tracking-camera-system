#pragma once
struct MockEEPROM {
  unsigned char read(int) { return 255; }
  void update(int, unsigned char) {}
};
static MockEEPROM EEPROM;
