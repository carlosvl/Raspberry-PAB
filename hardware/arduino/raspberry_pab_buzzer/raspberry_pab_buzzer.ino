// Buzzer firmware derived from working pin-test base (CH340 Nano).
const int BUZZER_PIN = 3;

void buzzerOff() {
  digitalWrite(BUZZER_PIN, HIGH);
}

void beepTimes(int count, int beepMs, int gapMs) {
  for (int i = 0; i < count; i++) {
    digitalWrite(BUZZER_PIN, LOW);
    delay(beepMs);
    digitalWrite(BUZZER_PIN, HIGH);
    if (i < count - 1) {
      delay(gapMs);
    }
  }
}

void handleLine(const String &line) {
  if (line == "PING") {
    Serial.println(F("PONG"));
    return;
  }
  if (line == "STOP") {
    buzzerOff();
    Serial.println(F("OK"));
    return;
  }
  if (line.startsWith("BEEP ")) {
    int freq = 0;
    int volume = 0;
    int count = 0;
    int beepMs = 0;
    int gapMs = 0;
    int parsed = sscanf(
      line.c_str(),
      "BEEP %d %d %d %d %d",
      &freq,
      &volume,
      &count,
      &beepMs,
      &gapMs
    );
    if (parsed != 5) {
      Serial.println(F("ERR beep"));
      return;
    }
    (void)freq;
    (void)volume;
    beepTimes(count, beepMs, gapMs);
    Serial.println(F("OK"));
    return;
  }
  Serial.println(F("ERR unknown"));
}

void setup() {
  pinMode(BUZZER_PIN, OUTPUT);
  buzzerOff();
  Serial.begin(115200);
  while (!Serial) {
    ;
  }
  Serial.println(F("READY"));
}

void loop() {
  if (!Serial.available()) {
    return;
  }
  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) {
    return;
  }
  handleLine(line);
}
