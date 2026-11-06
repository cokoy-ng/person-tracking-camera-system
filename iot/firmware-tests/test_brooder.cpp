#include <cassert>
#include <limits>
#include <iostream>
#include "../firmware/brooder/control.h"
#include "../firmware/brooder/alarm_policy.h"
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
  CycleSelector select;
  assert(select.select(1)==0 && select.select(1)==1);
  assert(select.select(2)==0 && select.select(2)==2);
  assert(select.select(0)==0 && select.select(3)==0);
  assert(select.select(8)==0 && select.select(8)==4);
  for (uint8_t id=1; id<=4; ++id) {
    const auto& p=CYCLES[id-1];
    const float ct=p.maxTemp-0.5f, ch=(p.minHumidity+p.maxHumidity)/2.0f;
    ClimateControl heating;
    heating.sample(p.maxTemp-1,ch,id,true,0); assert(heating.heater);
    heating.sample(p.maxTemp-0.1f,ch,id,true,5000); assert(heating.heater);
    heating.sample(p.maxTemp,ch,id,true,6000); assert(!heating.heater);
    heating.sample(p.maxTemp-1,ch,id,true,65000); assert(heating.heater == (p.maxTemp-1<=p.minTemp));
    heating.sample(p.maxTemp-1,ch,id,true,66000); assert(heating.heater);
    heating.sample(p.maxTemp+1,ch,id,true,66001); assert(!heating.heater);
    heating.sample(p.maxTemp-1,ch,id,false,66002); assert(!heating.heater);
    ClimateControl c;
    c.sample(ct,ch,id,true,0);
    assert(!c.heater && !c.humidifier && !c.ventilation && !c.reasons);
    // D7 eleva HR; el foco espera su intervalo antes de encender.
    c.sample(p.maxTemp-1,ch-2,id,true,15000);
    assert(c.heater==(p.maxTemp-1<=p.minTemp) && !c.humidifier && !c.ventilation && !c.reasons && c.airReasons==0);
    c.sample(ct,ch,id,true,20000); assert(c.heater==(p.maxTemp-1<=p.minTemp) && !c.humidifier && !c.ventilation);
    c.sample(p.maxTemp,ch+2,id,true,30000);
    assert(!c.heater && !c.humidifier && c.ventilation && !c.reasons && c.airReasons==3);
    c.sample(p.maxTemp-1,ch,id,true,31000);
    if(id!=1) assert(c.ventilation); // ciclo1: minimo corta inmediatamente
    c.sample(p.maxTemp-1,ch,id,true,45000); assert(!c.ventilation);
    c.sample(ct,ch+2,id,true,60000); assert(c.ventilation && c.airReasons==2);
    c.sample(ct,ch+1,id,true,80000); assert(c.ventilation); // seca hasta centro
    c.sample(ct,ch,id,true,81000); assert(!c.ventilation);
    c.sample(ct,p.maxHumidity,id,true,81001); assert(c.ventilation); // maximo inmediato
    c.sample(p.minTemp,p.maxHumidity,id,true,81002);
    assert(!c.ventilation && c.airReasons==10); // frio bloquea renovacion con HR alta
    c.sample(p.maxTemp,p.minHumidity-1,id,true,81003);
    assert(c.ventilation && !c.humidifier && !c.heater && c.airReasons==1);
    c.sample(p.minTemp-1,p.minHumidity-1,id,true,100000);
    assert(c.heater && !c.humidifier && !c.ventilation && c.reasons==5);
    c.sample(p.maxTemp+1,p.maxHumidity+1,id,true,100001);
    assert(c.reasons==10 && !c.heater && !c.humidifier && c.ventilation);
    c.sample(0,0,id,false,100002);
    assert(!c.humidifier && !c.ventilation && !c.heater && c.reasons==16 && c.airReasons==0 && c.climate==Climate::Fault);
    DoorPolicy dp;
    assert(dp.sample(p.maxTemp,true,0,p.maxTemp)==DoorAction::Close);
    assert(dp.sample(p.maxTemp+1,true,1,p.maxTemp)==DoorAction::Hold);
    assert(dp.sample(p.maxTemp+1,true,300001,p.maxTemp)==DoorAction::Hold);
    assert(dp.sample(p.maxTemp+1,true,300002,p.maxTemp)==DoorAction::Open);
  }
  // Same environment, different cable: adopt new ranges immediately.
  ClimateControl change;
  change.sample(32,55,1,true,0); assert(change.heater && !change.humidifier && !change.ventilation);
  change.sample(32,55,2,true,1); assert(!change.heater && !change.humidifier && change.ventilation);
  change.sample(32,55,3,true,2); assert(!change.heater && !change.humidifier && change.ventilation);
  change.sample(32,55,4,true,3); assert(!change.heater && !change.humidifier && change.ventilation);
  change.sample(32,55,1,true,4); assert(change.heater && !change.humidifier && !change.ventilation);
  for(uint8_t id=1;id<=4;++id) {
    const auto& p=CYCLES[id-1];
    change.sample(p.maxTemp,p.maxHumidity,id,true,100); assert(!change.heater && !change.humidifier && change.ventilation);
    change.sample(p.minTemp-1,p.minHumidity-1,id,true,101); assert(change.heater && !change.humidifier && !change.ventilation);
  }
  ClimateControl c;
  c.sample(35,75,1,true,0); assert(!c.heater && !c.humidifier && c.ventilation);
  c.sample(25.5,55,4,true,1); assert(c.heater && !c.humidifier && !c.ventilation && !c.reasons);
  c.sample(25,55,0,true,2); assert(c.climate==Climate::Fault);
  c.sample(25,55,5,true,3); assert(c.climate==Climate::Fault);
  c.sample(std::numeric_limits<float>::quiet_NaN(),55,1,true,4);
  assert(c.climate==Climate::Fault);
  c.sample(25,101,1,true,5); assert(c.climate==Climate::Fault);
  c.sample(35,75,1,true,UINT32_MAX-1000);
  c.tick(4998); assert(!c.heater && c.ventilation);
  c.tick(4999); assert(!c.heater && !c.humidifier && !c.ventilation && c.reasons==16);
  RelayDemand relay;
  assert(relay.update(true,false,0,15000));
  assert(relay.update(false,false,14999,15000));
  assert(!relay.update(false,false,15000,15000));
  assert(!relay.update(true,false,29999,15000));
  assert(relay.update(true,false,30000,15000));
  assert(!relay.update(true,true,30001,15000));
  assert(relay.update(true,false,30002,15000,true));
  assert(!relay.update(true,true,30003,15000,true)); // frio gana a maximoHR
  AlarmPolicy alarm;
  alarm.update(1,0); assert(alarm.pending && !alarm.active);
  alarm.update(1,29999); assert(!alarm.active);
  alarm.update(0,30000); assert(!alarm.active && !alarm.pending);
  alarm.update(1,40000); alarm.update(1,70000);
  assert(alarm.active && alarm.sounding && !alarm.pending);
  alarm.update(1,71000); assert(alarm.active && !alarm.sounding);
  alarm.update(1,130000); assert(alarm.sounding);
  alarm.update(0,130001); assert(!alarm.sounding && alarm.recovering);
  alarm.update(0,145000); assert(alarm.active);
  alarm.update(0,145001); assert(!alarm.active && !alarm.recovering);
  alarm.update(16,150000); alarm.update(16,159999); assert(!alarm.active);
  alarm.update(16,160000); assert(alarm.active);
  alarm.reset(); alarm.update(1,UINT32_MAX-1000); alarm.update(1,28999);
  assert(alarm.active && alarm.sounding);
  alarm.reset(); alarm.update(1,0); alarm.update(16,29000); alarm.update(16,30000);
  assert(!alarm.active); // Un nuevo tipo de fallo confirma su propio tiempo.
  std::cout << "OK: ciclos, centros, margenes, permanencia, fallos, puerta y alarmas temporizadas\n";
}
