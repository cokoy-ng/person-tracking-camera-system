// Host simulation of the actual sketch: no physical I/O.
#include <cassert>
#include <cstdint>
#include <string>
#include <sstream>
#include <iostream>
using byte = unsigned char;
const int LOW = 0, HIGH = 1, INPUT = 0, OUTPUT = 1, INPUT_PULLUP = 2;
const int LED_BUILTIN = 13;
int pins[20] = {}, modes[20] = {};
uint32_t clockMs = 0;
uint32_t millis() { return clockMs; }
void digitalWrite(int pin, int value) { pins[pin] = value; }
int digitalRead(int pin) { return pins[pin]; }
void pinMode(int pin, int mode) {
  modes[pin] = mode;
  if (mode == INPUT_PULLUP) pins[pin] = HIGH;
}
struct MockSerial {
  std::string input;
  std::ostringstream output;
  void begin(int) {}
  int available() { return input.size(); }
  char read() { char c = input[0]; input.erase(0, 1); return c; }
  template <typename T> void print(T value) { output << value; }
  template <typename T> void println(T value) { output << value << '\n'; }
} Serial;
#include "../firmware/servo_usb/servo_usb.ino"

void send(const std::string& text, const std::string& expected) {
  Serial.output.str("");
  Serial.input = text + "\n";
  loop();
  assert(Serial.output.str() == expected + "\n");
}

int main() {
  setup();
  assert(pins[3] != RELAY_ACTIVE_LEVEL);
  loop();
  assert(!light.on); // Initial resting level must not trigger the relay.
  send("SOUND OFF", "OK SOUND OFF");
  pins[4] = LOW;
  loop();
  assert(!light.on); // Uninstalled sensor is disabled.
  send("LIGHT PING", "OK LIGHT_1");
  send("LIGHT HOLD 2", "OK LIGHT HOLD 2");
  send("LIGHT HOLD 0", "ERR HOLD");
  send("LIGHT HOLD 5x", "ERR HOLD");
  assert(light.holdMs == 2000);
  send("LIGHT PERSON", "OK LIGHT PERSON");
  assert(pins[3] == RELAY_ACTIVE_LEVEL);
  send("SET 45", "OK 45");
  send("STOP", "OK STOP");
  assert(!servo.attached() && light.on); // Servo pause doesn't extinguish light.
  clockMs = 1999;
  loop();
  assert(light.on);
  send("LIGHT PERSON", "OK LIGHT PERSON");
  clockMs = 3000;
  loop();
  assert(light.on); // Presence renewed the timer.
  clockMs = 3999;
  loop();
  assert(!light.on);
  send("SOUND LOW", "OK SOUND LOW");
  pins[4] = LOW;
  loop();
  assert(light.on); // Sound works without camera messages.
  pins[4] = HIGH;
  clockMs += 2000;
  loop();
  assert(!light.on);
  send("SOUND OFF", "OK SOUND OFF");
  pins[4] = LOW;
  send("SOUND HIGH", "OK SOUND HIGH");
  pins[4] = HIGH;
  loop();
  assert(light.on);
  send("SOUND OFF", "OK SOUND OFF");
  clockMs += 2000;
  loop();
  assert(!light.on);
  clockMs = UINT32_MAX - 100;
  send("LIGHT PERSON", "OK LIGHT PERSON");
  clockMs += 1999;
  loop();
  assert(light.on);
  ++clockMs;
  loop();
  assert(!light.on && pins[3] != RELAY_ACTIVE_LEVEL);
  pins[4] = HIGH;
  send("SOUND CHANGE", "OK SOUND CHANGE");
  send("SOUND READ", "OK SOUND HIGH");
  assert(!light.on);
  pins[4] = LOW;
  loop();
  assert(light.on && pins[3] == HIGH);
  clockMs += 2000;
  loop();
  assert(!light.on); // A fixed input doesn't keep renewing the light.
  pins[4] = HIGH;
  loop();
  assert(!light.on); // Return to idle is not a second sound.
  // Two minutes of visible person must not time out after the first 30s.
  send("SOUND OFF", "OK SOUND OFF");
  send("LIGHT HOLD 30", "OK LIGHT HOLD 30");
  for (int i = 0; i < 240; ++i) {
    clockMs += 500;
    send("LIGHT PERSON", "OK LIGHT PERSON");
    assert(light.on && pins[3] == HIGH);
  }
  uint32_t lastPerson = clockMs;
  clockMs = lastPerson + 25000;
  pins[4] = HIGH;
  send("SOUND CHANGE", "OK SOUND CHANGE");
  pins[4] = LOW;
  loop(); // Sound renews the SAME timer, 25s after the person disappeared.
  clockMs = lastPerson + 30000;
  loop();
  assert(light.on);
  clockMs = lastPerson + 54999;
  loop();
  assert(light.on);
  clockMs = lastPerson + 55000;
  loop();
  assert(!light.on); // Off only 30s after the most recent of either source.
  pins[4] = HIGH;
  loop();
  pins[4] = LOW;
  loop(); // A new onset turns it on again.
  clockMs += 25000;
  send("LIGHT PERSON", "OK LIGHT PERSON"); // Person extends a sound trigger too.
  clockMs += 29999;
  loop();
  assert(light.on);
  ++clockMs;
  loop();
  assert(!light.on);
  // Physical D4 pulses: one ON, triple OFF, chatter doesn't add sounds.
  pins[4] = HIGH;
  send("SOUND CHANGE", "OK SOUND CHANGE");
  uint32_t before = soundGesture.events;
  for (int i = 0; i < 3; ++i) {
    clockMs += 400;
    pins[4] = LOW;
    loop();
    assert(light.on == (i < 2));
    pins[4] = HIGH;
    loop();
    clockMs += 10;
    pins[4] = LOW;
    loop(); // chatter from the same clap
    pins[4] = HIGH;
    loop();
  }
  assert(soundGesture.events == before + 3);
  assert(soundGesture.triples == 1);
  // New isolated clap turns ON after a completed triple.
  clockMs += 2000;
  pins[4] = LOW;
  loop();
  assert(light.on);
  pins[4] = HIGH;
  loop();
  // Continuous camera presence overrides triple OFF without dropping D3.
  send("SOUND CHANGE", "OK SOUND CHANGE");
  for (int i = 0; i < 3; ++i) {
    clockMs += 400;
    send("LIGHT PERSON", "OK LIGHT PERSON");
    pins[4] = LOW;
    loop();
    assert(light.on && pins[3] == HIGH);
    pins[4] = HIGH;
    loop();
  }
  assert(soundGesture.triples == 2);
  SoundGesture wrapped;
  uint32_t t = UINT32_MAX - 500;
  assert(wrapped.update(true, t) == 1);
  wrapped.update(false, t + 10);
  assert(wrapped.update(true, t + 400) == 1);
  wrapped.update(false, t + 410);
  assert(wrapped.update(true, t + 800) == -1);
  std::cout << "OK: relay, sound, serial protocol, timeout and clock wrap\n";
}
