#include <Servo.h>
#include <stdlib.h>
#include <string.h>

Servo servo;
const int PIN_SERVO = 2;
char line[32];
byte length = 0;
bool overflow = false;

void command() {
  if (strcmp(line, "PING") == 0) {
    Serial.println("PONG SERVO_USB_1");
  } else if (strcmp(line, "STOP") == 0) {
    servo.detach();
    digitalWrite(LED_BUILTIN, LOW);
    Serial.println("OK STOP");
  } else if (strncmp(line, "SET ", 4) == 0) {
    char *end;
    long angle = strtol(line + 4, &end, 10);
    if (end == line + 4 || *end != '\0' || angle < 0 || angle > 180) {
      Serial.println("ERR ANGLE");
      return;
    }
    // Match the working Arduino sketch: attach D2 before writing the angle.
    if (!servo.attached()) servo.attach(PIN_SERVO);
    servo.write((int)angle);
    digitalWrite(LED_BUILTIN, angle > 0 ? HIGH : LOW);
    Serial.print("OK ");
    Serial.println(angle);
  } else {
    Serial.println("ERR COMMAND");
  }
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);
  Serial.begin(115200);
  Serial.println("READY SERVO_USB_1");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      line[length] = '\0';
      if (overflow) Serial.println("ERR LENGTH");
      else command();
      length = 0;
      overflow = false;
    } else if (length < sizeof(line) - 1) {
      line[length++] = c;
    } else {
      overflow = true;
    }
  }
}
