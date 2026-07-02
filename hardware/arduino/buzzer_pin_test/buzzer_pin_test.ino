// Hardware smoke test: beep D3 every second + print on serial @ 115200.
const int BUZZER_PIN = 3;

void setup() {
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, HIGH);
  Serial.begin(115200);
  while (!Serial) {
    ;
  }
  Serial.println(F("PIN3TEST"));
}

void loop() {
  digitalWrite(BUZZER_PIN, LOW);
  delay(300);
  digitalWrite(BUZZER_PIN, HIGH);
  delay(700);
  Serial.println(F("BEEP"));
}
