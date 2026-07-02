// Low-level-trigger active buzzer on D3 (I/O pin pulled LOW = beep).
const int BUZZER_PIN = 3;

void setup() {
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, HIGH);  // idle silent
  Serial.begin(9600);
  Serial.println(F("Raspberry-PAB buzzer test ready"));
}

void loop() {
  Serial.println(F("beep"));
  digitalWrite(BUZZER_PIN, LOW);
  delay(300);
  digitalWrite(BUZZER_PIN, HIGH);
  delay(700);
}
