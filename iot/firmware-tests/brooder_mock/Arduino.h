#pragma once
#include <cstdint>
#include <cstring>
#include <cassert>
using byte = uint8_t;
const byte A0=14, A1=15, A2=16, A3=17, A4=18, A5=19;
const int LOW=0, HIGH=1, OUTPUT=1, INPUT_PULLUP=2;
#define F(x) x
static unsigned long mockTime=0;
static int levels[20]={};
static bool touched[20]={};
inline void pinMode(byte pin, int) { assert(pin<20); touched[pin]=true; }
inline void digitalWrite(byte pin, int value) { assert(pin<20); touched[pin]=true; levels[pin]=value; }
inline int digitalRead(byte) { return HIGH; }
inline unsigned long millis() { return mockTime; }
inline unsigned long micros() { static unsigned long us=0; return ++us; }
inline void delay(unsigned long ms) { mockTime+=ms; }
inline void delayMicroseconds(unsigned long) {}
struct MockSerial {
  void begin(unsigned long) {}
  int available() { return 0; }
  char read() { return 0; }
  template<typename T> void print(T) {}
  template<typename T> void println(T) {}
  void println() {}
};
static MockSerial Serial;
