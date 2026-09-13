#include <Servo.h>

Servo miServo;

const int PIN_SERVO = 2;

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);
  miServo.attach(PIN_SERVO);
  miServo.write(0);
  delay(1000);
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);  // LED L encendido: orden de ir a 60 grados
  miServo.write(60);  // Ir a 60 grados
  delay(1000);

  digitalWrite(LED_BUILTIN, LOW);   // LED L apagado: orden de regresar
  miServo.write(0);   // Regresar a 0 grados
  delay(1000);
}
