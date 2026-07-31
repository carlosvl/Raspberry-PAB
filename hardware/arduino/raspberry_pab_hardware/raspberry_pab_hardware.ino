// Combined buzzer (D3) + dual 8x32 WS2812 (D6) for Raspberry-PAB.
// Nano has 2KB SRAM: 220B BSS + 1536B pixel heap ≈ 292B stack left.
// Never use sscanf — it overflows that stack and corrupts the LED buffer.
#include <Adafruit_NeoPixel.h>
#include <avr/pgmspace.h>
#include <stdlib.h>
#include <string.h>

const uint8_t BUZZER_PIN = 3;
const uint8_t LED_PIN = 6;
const uint8_t TILE_W = 32;
const uint8_t TILE_H = 8;
const uint8_t MATRIX_W = 64;
const uint8_t MATRIX_H = 8;
const uint16_t LED_COUNT = 512;
const uint8_t SCROLL_MS = 50;
const uint8_t CHAR_W = 6;

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

// 5x7 font ASCII 32..90 in PROGMEM (flash, not SRAM).
const uint8_t FONT5X7[] PROGMEM = {
  0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x5F,0x00,0x00,0x00,0x07,0x00,0x07,0x00,
  0x14,0x7F,0x14,0x7F,0x14,0x24,0x2A,0x7F,0x2A,0x12,0x23,0x13,0x08,0x64,0x62,
  0x36,0x49,0x55,0x22,0x50,0x00,0x05,0x03,0x00,0x00,0x00,0x1C,0x22,0x41,0x00,
  0x00,0x41,0x22,0x1C,0x00,0x08,0x2A,0x1C,0x2A,0x08,0x08,0x08,0x3E,0x08,0x08,
  0x00,0x50,0x30,0x00,0x00,0x08,0x08,0x08,0x08,0x08,0x00,0x60,0x60,0x00,0x00,
  0x20,0x10,0x08,0x04,0x02,0x3E,0x51,0x49,0x45,0x3E,0x00,0x42,0x7F,0x40,0x00,
  0x42,0x61,0x51,0x49,0x46,0x21,0x41,0x45,0x4B,0x31,0x18,0x14,0x12,0x7F,0x10,
  0x27,0x45,0x45,0x45,0x39,0x3C,0x4A,0x49,0x49,0x30,0x01,0x71,0x09,0x05,0x03,
  0x36,0x49,0x49,0x49,0x36,0x06,0x49,0x49,0x29,0x1E,0x00,0x36,0x36,0x00,0x00,
  0x00,0x56,0x36,0x00,0x00,0x00,0x08,0x14,0x22,0x41,0x14,0x14,0x14,0x14,0x14,
  0x41,0x22,0x14,0x08,0x00,0x02,0x01,0x51,0x09,0x06,0x32,0x49,0x79,0x41,0x3E,
  0x7E,0x11,0x11,0x11,0x7E,0x7F,0x49,0x49,0x49,0x36,0x3E,0x41,0x41,0x41,0x22,
  0x7F,0x41,0x41,0x22,0x1C,0x7F,0x49,0x49,0x49,0x41,0x7F,0x09,0x09,0x01,0x01,
  0x3E,0x41,0x41,0x51,0x32,0x7F,0x08,0x08,0x08,0x7F,0x00,0x41,0x7F,0x41,0x00,
  0x20,0x40,0x41,0x3F,0x01,0x7F,0x08,0x14,0x22,0x41,0x7F,0x40,0x40,0x40,0x40,
  0x7F,0x02,0x04,0x02,0x7F,0x7F,0x04,0x08,0x10,0x7F,0x3E,0x41,0x41,0x41,0x3E,
  0x7F,0x09,0x09,0x09,0x06,0x3E,0x41,0x51,0x21,0x5E,0x7F,0x09,0x19,0x29,0x46,
  0x46,0x49,0x49,0x49,0x31,0x01,0x01,0x7F,0x01,0x01,0x3F,0x40,0x40,0x40,0x3F,
  0x1F,0x20,0x40,0x20,0x1F,0x7F,0x20,0x18,0x20,0x7F,0x63,0x14,0x08,0x14,0x63,
  0x03,0x04,0x78,0x04,0x03,0x61,0x51,0x49,0x45,0x43
};

int freeRam() {
  extern int __heap_start;
  extern void *__brkval;
  int top;
  return (int)&top - (__brkval == 0 ? (int)&__heap_start : (int)__brkval);
}

// Skip token; parse next signed int. Returns NULL on failure.
const char *parseInt(const char *s, int *out) {
  if (!s) return NULL;
  while (*s == ' ') s++;
  if (!(*s == '-' || (*s >= '0' && *s <= '9'))) return NULL;
  char *end = NULL;
  long v = strtol(s, &end, 10);
  if (end == s) return NULL;
  *out = (int)v;
  return end;
}

bool startsWith_P(const char *line, const char *progmemPrefix) {
  while (true) {
    char pc = (char)pgm_read_byte(progmemPrefix++);
    if (pc == '\0') return true;
    if (*line++ != pc) return false;
  }
}

uint16_t xyToIndex(int16_t x, int16_t y) {
  if (x < 0 || x >= MATRIX_W || y < 0 || y >= MATRIX_H) return 0xFFFF;
  uint8_t panel = (uint8_t)(x / TILE_W);
  uint8_t lx = (uint8_t)(x % TILE_W);
  uint16_t base = (uint16_t)panel * (TILE_W * TILE_H);
  uint16_t local = (lx & 1)
    ? (uint16_t)lx * TILE_H + (TILE_H - 1 - y)
    : (uint16_t)lx * TILE_H + y;
  return base + local;
}

void setXY(int16_t x, int16_t y, uint32_t color) {
  uint16_t idx = xyToIndex(x, y);
  if (idx != 0xFFFF) strip.setPixelColor(idx, color);
}

void buzzerOff() { digitalWrite(BUZZER_PIN, HIGH); }

void beepTimes(int count, int beepMs, int gapMs) {
  for (int i = 0; i < count; i++) {
    digitalWrite(BUZZER_PIN, LOW);
    delay(beepMs);
    digitalWrite(BUZZER_PIN, HIGH);
    if (i < count - 1) delay(gapMs);
  }
}

void matrixFill(uint8_t r, uint8_t g, uint8_t b) {
  uint32_t c = strip.Color(r, g, b);
  for (uint16_t i = 0; i < LED_COUNT; i++) strip.setPixelColor(i, c);
  strip.show();
}

void matrixClear() {
  strip.clear();
  strip.show();
}

void drawChar5x7(int16_t x, int16_t y, char c, uint32_t color) {
  if (c >= 'a' && c <= 'z') c = (char)(c - 'a' + 'A');
  if (c < 32 || c > 90) c = '?';
  uint8_t index = (uint8_t)(c - 32);
  for (uint8_t col = 0; col < 5; col++) {
    uint8_t bits = pgm_read_byte(&FONT5X7[index * 5 + col]);
    for (uint8_t row = 0; row < 7; row++) {
      if (bits & (1 << row)) setXY(x + col, y + row, color);
    }
  }
}

void drawText(int16_t x, int16_t y, const char *text, uint32_t color) {
  int16_t cursor = x;
  while (*text) {
    drawChar5x7(cursor, y, *text++, color);
    cursor += CHAR_W;
  }
}

void runSolid(uint8_t r, uint8_t g, uint8_t b, unsigned long ms) {
  matrixFill(r, g, b);
  delay(ms);
  matrixClear();
}

void runFlash(uint8_t r, uint8_t g, uint8_t b, unsigned long ms, unsigned long interval) {
  unsigned long endAt = millis() + ms;
  bool on = true;
  unsigned long last = millis();
  while (millis() < endAt) {
    if (millis() - last >= interval) { on = !on; last = millis(); }
    if (on) matrixFill(r, g, b); else matrixClear();
    delay(10);
  }
  matrixClear();
}

void runChase(uint8_t r, uint8_t g, uint8_t b, unsigned long ms) {
  unsigned long endAt = millis() + ms;
  int pos = 0, dir = 1;
  while (millis() < endAt) {
    strip.clear();
    strip.setPixelColor(pos, strip.Color(r, g, b));
    strip.show();
    pos += dir;
    if (pos >= (int)LED_COUNT - 1) dir = -1;
    else if (pos <= 0) dir = 1;
    delay(40);
  }
  matrixClear();
}

void runScroll(uint8_t r, uint8_t g, uint8_t b, unsigned long ms, const char *text) {
  char fallback[4];
  if (!text || !text[0]) {
    fallback[0] = 'P'; fallback[1] = 'A'; fallback[2] = 'B'; fallback[3] = '\0';
    text = fallback;
  }
  uint32_t color = strip.Color(r, g, b);
  int16_t textW = 0;
  for (const char *p = text; *p; p++) textW += CHAR_W;
  int16_t x = MATRIX_W;
  // Frame count (not millis): show() blocks interrupts so millis drifts.
  unsigned long frames = ms / SCROLL_MS;
  if (frames < 1) frames = 1;
  for (unsigned long i = 0; i < frames; i++) {
    strip.clear();
    drawText(x, 0, text, color);
    strip.show();
    delay(SCROLL_MS);
    x -= 1;
    if (x < -textW) x = MATRIX_W;
  }
  matrixClear();
}

void handleLine(char *line) {
  if (strcmp_P(line, PSTR("PING")) == 0) { Serial.println(F("PONG")); return; }
  if (strcmp_P(line, PSTR("INFO")) == 0) {
    Serial.print(F("PIXELS "));
    Serial.print(strip.numPixels());
    Serial.print(F(" FREE "));
    Serial.println(freeRam());
    return;
  }
  if (strcmp_P(line, PSTR("STOP")) == 0 || strcmp_P(line, PSTR("CLEAR")) == 0) {
    if (line[0] == 'S') buzzerOff();
    matrixClear();
    Serial.println(F("OK"));
    return;
  }
  if (startsWith_P(line, PSTR("BEEP "))) {
    int freq, vol, count, beepMs, gapMs;
    const char *p = line + 5;
    p = parseInt(p, &freq); if (!p) { Serial.println(F("ERR beep")); return; }
    p = parseInt(p, &vol); if (!p) { Serial.println(F("ERR beep")); return; }
    p = parseInt(p, &count); if (!p) { Serial.println(F("ERR beep")); return; }
    p = parseInt(p, &beepMs); if (!p) { Serial.println(F("ERR beep")); return; }
    p = parseInt(p, &gapMs); if (!p) { Serial.println(F("ERR beep")); return; }
    (void)freq; (void)vol;
    beepTimes(count, beepMs, gapMs);
    Serial.println(F("OK"));
    return;
  }
  if (startsWith_P(line, PSTR("BRIGHT "))) {
    int brightness;
    if (!parseInt(line + 7, &brightness) || brightness < 0 || brightness > 255) {
      Serial.println(F("ERR bright")); return;
    }
    strip.setBrightness((uint8_t)brightness);
    Serial.println(F("OK"));
    return;
  }
  if (startsWith_P(line, PSTR("FLASH "))) {
    int r, g, b, ms, interval;
    const char *p = line + 6;
    p = parseInt(p, &r); if (!p) { Serial.println(F("ERR flash")); return; }
    p = parseInt(p, &g); if (!p) { Serial.println(F("ERR flash")); return; }
    p = parseInt(p, &b); if (!p) { Serial.println(F("ERR flash")); return; }
    p = parseInt(p, &ms); if (!p) { Serial.println(F("ERR flash")); return; }
    p = parseInt(p, &interval); if (!p) { Serial.println(F("ERR flash")); return; }
    runFlash(r, g, b, ms, interval);
    Serial.println(F("OK"));
    return;
  }
  if (startsWith_P(line, PSTR("SOLID "))) {
    int r, g, b, ms;
    const char *p = line + 6;
    p = parseInt(p, &r); if (!p) { Serial.println(F("ERR solid")); return; }
    p = parseInt(p, &g); if (!p) { Serial.println(F("ERR solid")); return; }
    p = parseInt(p, &b); if (!p) { Serial.println(F("ERR solid")); return; }
    p = parseInt(p, &ms); if (!p) { Serial.println(F("ERR solid")); return; }
    runSolid(r, g, b, ms);
    Serial.println(F("OK"));
    return;
  }
  if (startsWith_P(line, PSTR("SCROLL "))) {
    int r, g, b, ms;
    const char *p = line + 7;
    p = parseInt(p, &r); if (!p) { Serial.println(F("ERR scroll")); return; }
    p = parseInt(p, &g); if (!p) { Serial.println(F("ERR scroll")); return; }
    p = parseInt(p, &b); if (!p) { Serial.println(F("ERR scroll")); return; }
    p = parseInt(p, &ms); if (!p) { Serial.println(F("ERR scroll")); return; }
    while (*p == ' ') p++;
    runScroll(r, g, b, ms, p);
    Serial.println(F("OK"));
    return;
  }
  if (startsWith_P(line, PSTR("CHASE "))) {
    int r, g, b, ms;
    const char *p = line + 6;
    p = parseInt(p, &r); if (!p) { Serial.println(F("ERR chase")); return; }
    p = parseInt(p, &g); if (!p) { Serial.println(F("ERR chase")); return; }
    p = parseInt(p, &b); if (!p) { Serial.println(F("ERR chase")); return; }
    p = parseInt(p, &ms); if (!p) { Serial.println(F("ERR chase")); return; }
    runChase(r, g, b, ms);
    Serial.println(F("OK"));
    return;
  }
  Serial.println(F("ERR unknown"));
}

void setup() {
  pinMode(BUZZER_PIN, OUTPUT);
  buzzerOff();
  pinMode(LED_PIN, OUTPUT);
  strip.begin();
  strip.setBrightness(64);
  strip.show();  // clear any residual pixels; keep boot quiet for admin tests
  Serial.begin(115200);
  while (!Serial) { ; }
  Serial.print(F("READY PIXELS "));
  Serial.print(strip.numPixels());
  Serial.print(F(" FREE "));
  Serial.println(freeRam());
}

void loop() {
  if (!Serial.available()) return;
  char line[64];
  size_t n = Serial.readBytesUntil('\n', line, sizeof(line) - 1);
  line[n] = '\0';
  while (n > 0 && (line[n - 1] == '\r' || line[n - 1] == ' ')) line[--n] = '\0';
  if (n == 0) return;
  handleLine(line);
}
