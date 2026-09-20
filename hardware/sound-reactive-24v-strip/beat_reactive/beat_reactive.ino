// Sound-reactive driver for a 24V 4-wire LED neon (pads +24V / G / R / D).
// ESP32: data GPIO 16, analog mic GPIO 34 (MAX9814 OUT).
// Power the strip from a fused 24V pack. ESP32 from a 24V→5V buck. Common GND.
//
// Arduino Zero: LED_PIN 6, MIC_PIN A0, 5V from the same buck into Zero 5V.

#include <Adafruit_NeoPixel.h>

#define MODE_DIGITAL 0
#define MODE_ANALOG 1

const int STRIP_MODE = MODE_DIGITAL;  // MODE_ANALOG if MOSFETs on G/R/D

const int LED_PIN = 16;     // strip D (digital) or MOSFET for D (analog)
const int ANALOG_G_PIN = 17;
const int ANALOG_R_PIN = 18;
const int MIC_PIN = 34;

// 24V WS2811 is often 1 pixel per 3 LEDs (60 LED/m → 20). One-IC-per-LED → 60/m.
const int LED_COUNT = 20;
const int BRIGHTNESS = 64;  // keep modest on battery
const uint8_t COLOR_ORDER = NEO_GRB + NEO_KHZ800;

const int SAMPLE_MS = 8;
const int REFRACTORY_MS = 140;
const float BEAT_RATIO = 1.45f;
const float ENV_ATTACK = 0.35f;
const float ENV_DECAY = 0.08f;
const float AVG_DECAY = 0.015f;
const int FLASH_DECAY = 12;

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, COLOR_ORDER);

float envelope = 0;
float baseline = 8;
int flash = 0;
unsigned long lastBeatMs = 0;
unsigned long lastSampleMs = 0;
uint16_t hue = 0;

#ifdef ESP32
int analogMax() { return 4095; }
#else
int analogMax() { return 1023; }
#endif

int readMicDeviation() {
  long acc = 0;
  const int n = 48;
  for (int i = 0; i < n; i++) {
    int v = analogRead(MIC_PIN);
    acc += v;
  }
  float mean = acc / (float)n;
  float dc = analogMax() * 0.5f;
  return (int)fabsf(mean - dc);
}

void analogWriteRgb(int r, int g, int b) {
  analogWrite(ANALOG_R_PIN, (r * BRIGHTNESS) / 255);
  analogWrite(ANALOG_G_PIN, (g * BRIGHTNESS) / 255);
  analogWrite(LED_PIN, (b * BRIGHTNESS) / 255);
}

void showDigital(uint8_t r, uint8_t g, uint8_t b) {
  for (int i = 0; i < LED_COUNT; i++) {
    strip.setPixelColor(i, strip.Color(r, g, b));
  }
  strip.show();
}

void showColor(uint8_t r, uint8_t g, uint8_t b) {
  if (STRIP_MODE == MODE_ANALOG) {
    analogWriteRgb(r, g, b);
  } else {
    showDigital(r, g, b);
  }
}

void setup() {
  Serial.begin(115200);
#ifdef ESP32
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);
#endif
  pinMode(MIC_PIN, INPUT);

  if (STRIP_MODE == MODE_ANALOG) {
    pinMode(LED_PIN, OUTPUT);
    pinMode(ANALOG_G_PIN, OUTPUT);
    pinMode(ANALOG_R_PIN, OUTPUT);
    analogWriteRgb(0, 0, 0);
  } else {
    strip.begin();
    strip.setBrightness(BRIGHTNESS);
    strip.show();
  }

  delay(200);
  Serial.println("READY SOUND-REACTIVE");
  Serial.println(STRIP_MODE == MODE_DIGITAL ? "MODE digital" : "MODE analog");

  showColor(255, 0, 0);
  delay(250);
  showColor(0, 255, 0);
  delay(250);
  showColor(0, 0, 255);
  delay(250);
  showColor(0, 0, 0);
}

void wheel(uint16_t pos, uint8_t val, uint8_t *r, uint8_t *g, uint8_t *b) {
  pos = pos & 255;
  uint8_t r0, g0, b0;
  if (pos < 85) {
    r0 = 255 - pos * 3;
    g0 = 0;
    b0 = pos * 3;
  } else if (pos < 170) {
    pos -= 85;
    r0 = 0;
    g0 = pos * 3;
    b0 = 255 - pos * 3;
  } else {
    pos -= 170;
    r0 = pos * 3;
    g0 = 255 - pos * 3;
    b0 = 0;
  }
  *r = (uint8_t)((r0 * val) / 255);
  *g = (uint8_t)((g0 * val) / 255);
  *b = (uint8_t)((b0 * val) / 255);
}

void loop() {
  unsigned long now = millis();
  if (now - lastSampleMs < (unsigned long)SAMPLE_MS) {
    return;
  }
  lastSampleMs = now;

  int level = readMicDeviation();
  if (level > envelope) {
    envelope = envelope + (level - envelope) * ENV_ATTACK;
  } else {
    envelope = envelope + (level - envelope) * ENV_DECAY;
  }
  baseline = baseline + (envelope - baseline) * AVG_DECAY;
  if (baseline < 4) {
    baseline = 4;
  }

  if (envelope > baseline * BEAT_RATIO && (now - lastBeatMs) > (unsigned long)REFRACTORY_MS) {
    lastBeatMs = now;
    flash = 255;
    hue = hue + 40;
    if (hue > 255) {
      hue = 0;
    }
    Serial.print("BEAT env=");
    Serial.print(envelope, 1);
    Serial.print(" base=");
    Serial.println(baseline, 1);
  }

  if (flash > FLASH_DECAY) {
    flash -= FLASH_DECAY;
  } else {
    flash = 0;
  }

  uint8_t val = (uint8_t)flash;
  if (val < 8 && envelope > baseline) {
    val = (uint8_t)constrain((int)(envelope / 2.0f), 0, 40);
  }

  uint8_t r, g, b;
  wheel(hue, val, &r, &g, &b);
  showColor(r, g, b);
}
