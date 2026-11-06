#include <cassert>
#include <cstdio>
#include <initializer_list>
#include "manual_outputs.h"
#include "protocol.h"
int main() {
 ManualOutputs m;
 for(int i=0;i<5;++i) {
  m.set(i,2,0); assert(m.output(i,false,false)); assert(!m.output(i,true,true));
  m.set(i,1,0); assert(!m.output(i,true,false));
  m.set(i,0,0); assert(m.output(i,true,false));
 }
 m.set(0,2,0); m.tick(59999); assert(m.modes[0]==2);
 m.tick(60000); assert(m.modes[0]==0);
 m.set(1,1,UINT32_MAX-1000); m.tick(58999); assert(m.modes[1]==0);
 assert(decodeCommand("~H48")=='H'); assert(!decodeCommand("~H49"));
 m.set(2,1,100,300000UL);m.tick(60100);assert(m.modes[2]==1);
 m.tick(300100);assert(m.modes[2]==0);
 m.set(3,1,0,0);m.tick(86400000UL);assert(m.modes[3]==1);
 m.set(3,0,86400001UL);assert(m.modes[3]==0);
 uint8_t index,mode;uint32_t seconds;
 for(const char* payload : {"!110","!12300","!4286400"}) {
   uint8_t sum=0;for(const char* p=payload;*p;++p)sum^=*p;
   char frame[20];std::snprintf(frame,sizeof(frame),"%s*%02X",payload,sum);
   assert(decodeManual(frame,index,mode,seconds));
   frame[2]='9';assert(!decodeManual(frame,index,mode,seconds));
 }
 assert(!decodeManual("!1186401*00",index,mode,seconds));
}
