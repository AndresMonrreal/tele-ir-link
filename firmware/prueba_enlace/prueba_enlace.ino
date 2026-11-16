const int LED_IR_PIN = 18;
const int IR_PIN = 4;
const int FREQ = 38000;

volatile unsigned long cambios = 0;

void IRAM_ATTR alCambiar() {
  cambios++;
}

void setup() {
  Serial.begin(115200);
  pinMode(IR_PIN, INPUT);
  attachInterrupt(digitalPinToInterrupt(IR_PIN), alCambiar, CHANGE);
  ledcAttach(LED_IR_PIN, FREQ, 8);
  ledcWrite(LED_IR_PIN, 0);
}

void rafaga(int ms) {
  unsigned long fin = millis() + ms;
  while (millis() < fin) {
    ledcWrite(LED_IR_PIN, 128);
    delayMicroseconds(600);
    ledcWrite(LED_IR_PIN, 0);
    delayMicroseconds(600);
  }
}

void loop() {
  cambios = 0;
  rafaga(200);
  unsigned long conLed = cambios;

  cambios = 0;
  delay(200);
  unsigned long sinLed = cambios;

  Serial.printf("Con LED: %lu cambios   |   Sin LED: %lu cambios\n", conLed, sinLed);
  delay(600);
}