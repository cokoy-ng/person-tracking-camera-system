#include <cassert>
#include <limits>
#include <iostream>
#include "../firmware/brooder/control.h"
#include "../firmware/brooder/door.h"
#include "../firmware/brooder/protocol.h"

int main() {
  assert(decodeCommand("~S53") == 'S');
  assert(decodeCommand("~O4F") == 'O');
  assert(decodeCommand("~A41") == 'A');
  assert(decodeCommand("~O53") == 0);
  assert(decodeCommand("~S5") == 0);
  assert(decodeCommand("~S5X") == 0);
  assert(decodeCommand("garbage~S53") == 0);
  assert(decodeCommand("") == 0);
  DoorPolicy policy;
  assert(policy.sample(28, true, 0) == DoorAction::Close);
  assert(policy.sample(25, true, 1) == DoorAction::Close);
  assert(policy.sample(32, true, 2) == DoorAction::Close);
  assert(policy.sample(33, true, 10) == DoorAction::Hold);
  assert(policy.sample(33, true, 300010) == DoorAction::Hold);
  assert(policy.sample(33, true, 300011) == DoorAction::Open);
  assert(policy.sample(32, true, 300020) == DoorAction::Close);
  assert(policy.sample(33, true, 300030) == DoorAction::Hold);
  assert(policy.sample(33, false, 600000) == DoorAction::Hold);
  assert(policy.sample(33, true, 600031) == DoorAction::Hold);
  policy.reset();
  assert(policy.sample(33, true, UINT32_MAX - 1000) == DoorAction::Hold);
  assert(policy.sample(33, true, 299000) == DoorAction::Open);
  policy.reset();
  Door startup;
  startup.reference(false);
  assert(policy.sample(35, true, 0) == DoorAction::Hold);
  assert(startup.position == 0 && !startup.moving());
  Door d;
  d.request(true);
  assert(!d.moving() && d.step() == 0);
  d.reference(false);
  d.request(true);
  for (int i=0; i<100; ++i) assert(d.step() == 1);
  d.request(false);
  for (int i=0; i<100; ++i) assert(d.step() == -1);
  assert(d.position == 0 && !d.moving() && d.step() == 0);
  d.request(true);
  for (int32_t i=0; i<Door::TRAVEL; ++i) assert(d.step() == 1);
  assert(d.position == 49152 && !d.moving() && d.step() == 0);
  d.request(true);
  assert(!d.moving());
  d.request(false);
  for (int32_t i=0; i<Door::TRAVEL; ++i) assert(d.step() == -1);
  assert(d.position == 0 && !d.moving());
  ClimateControl c;
  c.tick(0);
  assert(!c.heater && c.alarm && c.climate == Climate::Fault);
  c.sample(25, true, 10);
  assert(c.heater && c.alarm && c.climate == Climate::Cold);
  c.sample(26, true, 20);
  assert(c.heater && !c.alarm);
  c.sample(27, true, 30);
  assert(c.heater && !c.alarm);
  c.sample(29.9f, true, 31);
  assert(c.heater && !c.alarm);
  c.sample(30, true, 32);
  assert(!c.heater && !c.alarm);
  c.sample(29, true, 33);
  assert(!c.heater && !c.alarm);
  c.sample(26.2f, true, 40);
  assert(!c.heater && !c.alarm);
  c.sample(32, true, 50);
  assert(!c.heater && !c.alarm);
  c.sample(32.1f, true, 60);
  assert(!c.heater && c.alarm && c.climate == Climate::Hot);
  c.sample(25, true, 70);
  c.sample(25, false, 80);
  assert(!c.heater && c.alarm && c.climate == Climate::Fault);
  c.sample(25, true, 100);
  c.tick(6099);
  assert(c.heater);
  c.tick(6100);
  assert(!c.heater && c.alarm);
  c.sample(std::numeric_limits<float>::quiet_NaN(), true, 6200);
  assert(c.climate == Climate::Fault);
  c.sample(std::numeric_limits<float>::infinity(), true, 6300);
  assert(c.climate == Climate::Fault);
  c.sample(25, true, UINT32_MAX - 1000);
  c.tick(4998);
  assert(c.heater);
  c.tick(4999);
  assert(!c.heater && c.alarm);
  c.sample(29, true, 5000);
  assert(!c.heater && !c.alarm && c.climate == Climate::Normal);
  std::cout << "OK: thresholds, hysteresis, sensor failure, stale data, clock wrap\n";
}
