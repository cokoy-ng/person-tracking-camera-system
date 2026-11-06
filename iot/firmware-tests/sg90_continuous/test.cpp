#include <cassert>
#include <string>
#include <iostream>
#include <climits>
using byte = unsigned char;
#define F(x) x
#define OUTPUT 1
#define LOW 0
unsigned long now = 0;
unsigned long millis() { return now; }
void pinMode(int,int) {}
void digitalWrite(int,int) {}
struct SerialMock {
  std::string output;
  void begin(int) {}
  void println(const char *s) { output += std::string(s) + "\n"; }
  int available() { return 0; }
  char read() { return 0; }
} Serial;
#include "../../firmware/sg90_test/sg90_test.ino"
void send(const char *s) { strcpy(line,s); command(); }
int main() {
  setup(); assert(!motor.attached());
  send("SET 90"); assert(!motor.attached());
  send("CYCLE 501"); assert(!motor.attached());
  send("CYCLE 0"); assert(!motor.attached());
  send("CYCLE 200x"); assert(!motor.attached());
  send("CYCLE 200"); assert(phase==1 && motor.us==1600);
  now=199; updateCycle(); assert(phase==1);
  send("CYCLE 500"); assert(runMs==200 && phaseStart==0);
  now=200; updateCycle(); assert(phase==2 && motor.us==1500);
  now=3199; updateCycle(); assert(phase==2);
  now=3200; updateCycle(); assert(phase==3 && motor.us==1200);
  now=3399; updateCycle(); assert(phase==3);
  now=3400; updateCycle(); assert(phase==4 && motor.us==1500);
  now=3699; updateCycle(); assert(motor.attached());
  now=3700; updateCycle(); assert(!motor.attached() && phase==0);
  for (int stage=1; stage<=4; ++stage) {
    send("CYCLE 200");
    if(stage>=2) {now+=200; updateCycle();}
    if(stage>=3) {now+=3000; updateCycle();}
    if(stage>=4) {now+=200; updateCycle();}
    assert(phase==stage);
    send("STOP"); now+=10000; updateCycle();
    assert(phase==0 && !motor.attached());
  }
  now=ULONG_MAX-100; send("CYCLE 200");
  now=99; updateCycle(); assert(phase==2);
  send("STOP");
  for (const char *cmd : {"TURN R 200", "TURN L 200"}) {
    now=0; send(cmd); assert(phase==5);
    assert(motor.us == (cmd[5]=='R' ? 1600 : 1200));
    now=199; updateCycle(); assert(phase==5);
    now=200; updateCycle(); assert(phase==4 && motor.us==1500);
    now=500; updateCycle(); assert(phase==0 && !motor.attached());
    now=10000; updateCycle(); assert(phase==0 && !motor.attached());
  }
  now=0; send("TURN L 5000"); assert(phase==5);
  now=4999; updateCycle(); assert(phase==5);
  now=5000; updateCycle(); assert(phase==4);
  now=5300; updateCycle(); assert(phase==0 && !motor.attached());
  send("TURN R 19"); assert(phase==0);
  send("TURN R 5001"); assert(phase==0);
  send("TURN X 200"); assert(phase==0);
  send("TURN R 200x"); assert(phase==0);
  send("TURN R 200"); send("STOP");
  now+=500; updateCycle(); assert(phase==0 && !motor.attached());
  std::cout << "OK: tiempos, inversión, parada, límites, rechazo SET y rollover\n";
}
