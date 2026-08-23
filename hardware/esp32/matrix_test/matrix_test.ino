// Standalone WS2812B triple 8x32 matrix test (768 LEDs on GPIO 16).
// Daisy-chain: panel1 DOUT → panel2 DIN → panel3 DIN. Upload to verify wiring.
#include <Adafruit_NeoPixel.h>

const int LED_PIN = 16;
const int LED_COUNT = 768;  // three 8x32 panels
const int BRIGHTNESS = 40;  // keep low — 768 LEDs need a strong 5V supply

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

uint32_t wheel(byte wheelPos) {
  wheelPos = 255 - wheelPos;
  if (wheelPos < 85) {
    return strip.Color(255 - wheelPos * 3, 0, wheelPos * 3);
  }
  if (wheelPos < 170) {
    wheelPos -= 85;
    return strip.Color(0, wheelPos * 3, 255 - wheelPos * 3);
  }
  wheelPos -= 170;
  return strip.Color(wheelPos * 3, 255 - wheelPos * 3, 0);
}

void colorWipe(uint32_t color, int waitMs) {
  for (int i = 0; i < LED_COUNT; i++) {
    strip.setPixelColor(i, color);
    strip.show();
    delay(waitMs);
  }
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  strip.begin();
  strip.setBrightness(BRIGHTNESS);
  strip.show();

  Serial.begin(115200);
  delay(200);
  Serial.println("READY");

  // Wipe should light panel 1 (0–255), panel 2 (256–511), then panel 3 (512–767)
  colorWipe(strip.Color(255, 0, 0), 4);
  colorWipe(strip.Color(0, 255, 0), 4);
  colorWipe(strip.Color(0, 0, 255), 4);
  strip.clear();
  strip.show();
}

void loop() {
  for (int j = 0; j < 256; j++) {
    for (int i = 0; i < LED_COUNT; i++) {
      strip.setPixelColor(i, wheel((i + j) & 255));
    }
    strip.show();
    delay(20);
  }
}
