// Keep low-level-trigger buzzer silent on D3.
const int BUZZER_PIN = 3;

void setup() {
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, HIGH);  // HIGH = off for low-level-trigger modules
}

void loop() {
  // idle
}
