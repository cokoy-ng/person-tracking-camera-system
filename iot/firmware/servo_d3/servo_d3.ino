#include <Servo.h>

Servo miServo;

void setup() {
  miServo.attach(3);  // Señal del servo en D3.
}

void loop() {
  miServo.write(180);
  delay(10000);  // 10 segundos.

  miServo.write(130);
  delay(3000);   // 3 segundos.
}
