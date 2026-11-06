// Prueba dedicada: Wire A4/A5, PCF8574 0x27 con mapa habitual MH/YwRobot.
// Usa hd44780 1.3.2. No controla sensores, motor, calefaccion ni ventilador.
#include <Wire.h>
#include <hd44780.h>
#include <hd44780ioClass/hd44780_I2Cexp.h>
hd44780_I2Cexp lcd(0x27, I2Cexp_PCF8574, 0,1,2,4,5,6,7,3,HIGH);
int initStatus = -99;
int memoryErrors = -1;
unsigned long last = 0;
void portProbe(byte value) {
  Wire.beginTransmission(0x27); Wire.write(value);
  byte result = Wire.endTransmission();
  delayMicroseconds(100);
  int count = Wire.requestFrom(0x27,1);
  int actual = count == 1 ? Wire.read() : -1;
  Serial.print(F("PCF WRITE=0x")); Serial.print(value, HEX);
  Serial.print(F(" READ=0x")); Serial.print(actual, HEX);
  Serial.print(F(" I2C_STATUS=")); Serial.println(result);
}
void setup() {
  Serial.begin(9600); delay(1000);
  Serial.println(F("LCD_FIXED_TEST UNO COM6 SDA=A4 SCL=A5"));
  Wire.begin(); Wire.setClock(100000); Wire.setWireTimeout(25000,true);
  // E=0 para estas pruebas: LCD no deberia conducir datos.
  portProbe(0xF0); portProbe(0xF1); portProbe(0xF2); portProbe(0xF8);
  lcd.setExecTimes(3000,100); // Tiempos conservadores para LCD lento.
  initStatus = lcd.begin(16,2);
  Serial.print(F("FIXED_BEGIN_STATUS=")); Serial.println(initStatus);
  Serial.println(F("BACKLIGHT TEST: tres ciclos OFF/ON, 0.8s cada fase"));
  for (byte i=0;i<3;++i) {
    lcd.noBacklight(); delay(800); lcd.backlight(); delay(800);
  }
  const char* rows[] = {"0123456789ABCDEF", "fedcba9876543210"};
  memoryErrors = 0;
  for (byte row=0;row<2;++row) {
    lcd.setCursor(0,row); lcd.print(rows[row]);
  }
  for (byte row=0;row<2;++row) {
    lcd.setCursor(0,row);
    for (byte col=0;col<16;++col) {
      int actual=lcd.read();
      if(actual != rows[row][col]) {
        ++memoryErrors;
        Serial.print(F("RAM row="));Serial.print(row);
        Serial.print(F(" col="));Serial.print(col);
        Serial.print(F(" expected="));Serial.print(int(rows[row][col]));
        Serial.print(F(" actual="));Serial.println(actual);
      }
    }
  }
  Serial.print(F("RAM_ERRORS="));Serial.println(memoryErrors);
  lcd.clear(); lcd.backlight();
  lcd.setCursor(0,0);lcd.print("PRUEBA LCD 1602A");
  lcd.setCursor(0,1);lcd.print("A4 SDA  A5 SCL");
  delay(3000);
}
void loop() {
  if(millis()-last>=1000) {
    last=millis();
    char row[17];snprintf(row,sizeof(row),"Segundos: %6lu",millis()/1000);
    lcd.setCursor(0,0);lcd.print("PRUEBA LCD 1602A");
    lcd.setCursor(0,1);lcd.print(row);
    Serial.print(F("UPTIME="));Serial.print(millis()/1000);
    Serial.print(F(" INIT="));Serial.print(initStatus);
    Serial.print(F(" RAM_ERRORS="));Serial.println(memoryErrors);
  }
}
