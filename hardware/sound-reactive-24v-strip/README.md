# Sound-reactive 24 V LED strip

Standalone build: drive the **silicone neon / 4-wire 24 V** string from a **mic beat**, using an **ESP32**. Not wired into the Raspberry-PAB kiosk matrix.

**Power:** prefer the strip’s **original 24 V DC wall brick** if you have it ([wall supply](#original-24-v-wall-supply)). Use a [battery pack](#power-budget-battery) only when you need it cordless.

The strip in the photos is labeled:

```text
+24V
G
R
D
```

with a **60/m** cut mark (`60K`) and an arrow. That is **24 V power**, not 5 V WS2812. The MCU only drives a **data / PWM** line. **Never put 24 V on an ESP32 or Arduino Zero pin.**

Use a **dedicated ESP32** (not the PAB matrix board). Arduino Zero can do the same circuit with different pins; ESP32 is the better fit (ADC/FFT, FastLED/WLED, 5 V VIN from a small buck).

The **MELK / Lotus Lamp X** strip from the kiosk is a different product. For a standalone beat light with no soldering, use that first — see [Kiosk MELK / Lotus Lamp strip](#kiosk-melk--lotus-lamp-strip).

---

## What this strip is

Four copper buses + 5050 LEDs + a tiny SMD between pixels is almost always one of:

| Type | `G` `R` `D` mean | How you drive it |
|------|------------------|------------------|
| **A — addressable (likely)** | `G` = GND, `D` = data, `R` = backup data or clock | One GPIO → `D` (WS2811 / GS8208 / similar) |
| **B — analog RGB, common anode** | `G` `R` `D` = three color cathodes (D ≈ blue) | Three N-MOSFETs PWM those pads to GND |

24 V addressable pixels are often **1 IC per 3 LEDs**, so 60 LEDs/m ≈ **20 pixels/m**. Count ICs or measure length after the smoke test.

### Identify it (2 minutes, power off)

1. Continuity from the `G` pad along the strip — it should be the ground pour.
2. Look at the first LED: if you see a small SOP IC (not just an 0805 resistor), it is type **A**.
3. Power **only** `+24V` and `G` (no data). Type **B** often glows faintly or not at all; type **A** stays dark until data arrives.
4. Run the digital smoke test in [`beat_reactive/`](beat_reactive/). If nothing lights, switch the sketch to analog mode and use the MOSFET wiring below.

---

## Recommendation

| Piece | Choice |
|-------|--------|
| MCU | **ESP32 DevKit** (the one you have). Skip Zero unless you already prefer it. |
| Firmware | Custom sketch here **or** [WLED](https://kno.wled.ge/) with Audio Reactive (phone UI, more effects). |
| Mic | **MAX9814** (AGC analog, easy) on ESP32 **GPIO 34**. Better: **INMP441** I2S if you flash WLED SR. Avoid bare KY-038 “clap” modules. |
| Strip power | **Original 24 V DC brick** if you have it. Battery pack only for cordless. |
| ESP32 power | USB charger (simplest with the wall brick) **or** a **24 V → 5 V buck** tapped from the same 24 V rail. |

Arduino Zero: 3.3 V only, `VIN`/`5V` must stay at **5 V**. Same buck and level shifter; LED pin **D6**, mic **A0**. No WLED.

---

## Kiosk MELK / Lotus Lamp strip

Yes — the **MELK-OT21** (Lotus Lamp X) ribbon the kiosk already flashes for reminders can be a standalone music light. Do **not** wire it like the 24 V neon. It is a sealed **BLE controller + 5 V (typical) strip**, not a raw data pin.

| Goal | Use |
|------|-----|
| Party / kick-reactive light tonight, no extra parts | **Lotus Lamp X app** music/mic mode (below) |
| Tight beat-sync, custom patterns, ESP32 | Bypass the BLE brick and drive the ribbon as pixels (optional) |
| Keep using it on the kiosk | Leave the box on; kiosk and the phone app **cannot** both connect |

The kiosk already does a **rainbow pulse** during Music Breaks. That is timed to the playlist, **not** the kick drum. True beat-follow is the app’s Music mode, or an ESP32 on a raw data line.

### Standalone (stock app) — no ESP32

1. Stop the kiosk from holding BLE: Admin LED off, or stop `raspberry-pab`, and close any leftover connection. The brick accepts **one** client.
2. Power the MELK controller from its original USB/wall supply (or a **5 V** USB battery pack into that same input — not 24 V).
3. Open **Lotus Lamp X**, connect to `MELKL-OT21 …`.
4. Open **♫ Music** (or Mic). Choose **Device MIC** if the controller box has a mic hole; otherwise **Phone MIC**.
5. Raise rhythm sensitivity; play music near that mic.

Leave the phone in range if you used Phone MIC. Device MIC can keep reacting after you background the app, depending on the brick firmware.

### Do / don’t (MELK)

| Do | Don’t |
|----|--------|
| Use the original controller + its 5 V supply | Feed the MELK box from the 24 V neon pack |
| Disconnect the Pi before the phone app | Expect ESP32 GPIO 16 to talk to the BLE dongle |
| Treat app music mode as “good enough strobe” | Expect per-LED chase latency like WLED |

BLE color updates are tens to hundreds of ms. Driving `set_rgb` from an ESP32/Pi on every kick is possible with `lotus-lamp`, but it will feel late and only paints the **whole** strip. Skip that for a beat light.

### Optional: bypass the BLE box

If you want the same ESP32 sketch as the 24 V build:

1. Unplug the ribbon from the MELK dongle (usually a 3- or 4-pin JST: **5 V, GND, DIN**).
2. Confirm with a meter: **5 V** on the red/V+ pin, not 12/24 V.
3. Wire like a normal WS2812: fused 5 V pack → strip 5 V/GND; ESP32 GND common; GPIO 16 → 330 Ω → **DIN**.
4. Set `LED_COUNT` to the actual pixel count (often 30 or 60 per meter, **one IC per LED**).

Keep the BLE box if you still want kiosk reminder flashes.

---

## Original 24 V wall supply

Using the strip’s **original brick** does not change the LED data circuit (GPIO 16 → 330 Ω → `D`, common GND, 1000 µF). It only replaces the battery pack on the **24 V rail**.

Confirm it is **24 V DC** (label `V⎓` / `24VDC`). A 24 V **AC** LED transformer is the wrong kind — do not tie that to the ESP32 ground scheme. Center-pin of a barrel jack is usually **+**; verify with a meter before soldering.

The brick is already sized for this ribbon. The ESP32 adds ~1 W. You can leave brightness higher than on battery (still start ~80–128).

### What drops vs battery

| Battery design | Wall-brick design |
|----------------|-------------------|
| 6S pack, BMS, pack fuse, runtime math | Brick + its own protection; inline fuse optional |
| Must buck 24 V → 5 V for the ESP32 | **Optional.** USB-C charger can power the ESP32 instead |
| 25.2 V fully charged 6S can over-volt a 24 V strip | Brick is already 24.0 V |

### Simplest: two cords (recommended)

Keep the original 24 V supply on the strip. Power the ESP32 from **USB** (phone brick or computer). You do **not** need a buck converter.

```text
24 V DC brick +  ──────── strip +24V
24 V DC brick −  ────┬─── strip G
                     └─── ESP32 GND     (required — data will not work without this)

USB 5 V charger    ────── ESP32 USB-C / 5V     (MCU only)
ESP32 GPIO 16 ── 330 Ω ── strip D
1000 µF 35 V across strip +24V and G at the input
```

Do **not** feed ESP32 `5V` from a buck **and** from USB at the same time. While programming: USB only for the MCU, 24 V brick on the strip, grounds tied.

### One cord: tap the brick

If you want a single wall plug, keep the battery circuit but substitute the pack with the brick:

```text
24 V DC brick + ── (optional fuse) ──┬── strip +24V
                                     └── buck VIN+  →  5.1 V  →  ESP32 5V
24 V DC brick − ─────────────────────┬── strip G
                                     ├── buck VIN−
                                     └── ESP32 GND
```

Same 24 V → 5 V buck (≥ 2 A) as the battery build. Unplug USB after upload, or don’t connect buck 5 V while USB is plugged in.

### Do / don’t (wall brick)

| Do | Don’t |
|----|--------|
| Tie brick − to ESP32 GND | Assume USB ground is enough without a wire to strip `G` |
| Leave the brick’s 24 V on strip `+24V` only | Put 24 V into ESP32 VIN / 5V / GPIO |
| Meter the brick: DC, ~24 V, polarity | Use a 24 V **AC** transformer as “close enough” |
| Cap still at the strip input | Power the strip from the ESP32 USB 5 V |

If the original supply went through a dimmer / RF box you no longer have, use only a bare **24 V DC** output onto `+24V` / `G`. The ESP32 replaces that box.

---

## Power budget (battery)

Strip current dominates. ESP32 is a rounding error after the buck.

| Load | Notes |
|------|--------|
| 24 V 60 LED/m RGB, **1 m**, full white | Plan **~0.6 A / ~14 W** (measure yours; 24 V pixels vary) |
| Same, beat-reactive, brightness cap ~80 | Often **~4–8 W** average |
| ESP32 + mic + buck loss | ~1 W from the 24 V pack |

**Pack options** (pick one):

- **6S Li-ion** (21–25.2 V) with BMS — closest to 24 V; do not charge above the strip’s 24 V rating if the pack hits 25.2 V. Prefer a 24 V LED-rated strip or a 24.0 V regulated output.
- **8S LiFePO₄** (~24–29 V) — **too high** unless you buck **down to 24.0 V** for the strip.
- **Two 12 V sealed/LiFePO₄ in series** with a 24 V fuse — simple if you already have 12 V batteries.
- USB power bank **boosted** 5 V → 24 V — works for a short piece; efficiency is worse than a 24 V pack.

**Runtime (example):** 1 m strip, ~6 W average, 24 V **2 Ah** (48 Wh) → **~6–7 h**. Size the fuse for **~2×** measured current (start with **3 A** for 1–2 m).

Keep firmware brightness **≤ 80** on battery. Inject 24 V at **both ends** if the run is longer than ~2 m.

---

## Circuit (type A — addressable)

Wall brick (two-cord) is above. Battery / one-cord tap:

```text
24 V + (brick or battery) ── fuse ── switch ──┬── strip +24V
                                              │
                                              ├── 1000 µF 35 V  (across strip +24V and G, at the input)
                                              │
                                              └── buck VIN+  →  5.1 V out  →  ESP32 5V
24 V − ───────────────────────────────────────┬── strip G
                                              ├── buck VIN−
                                              └── ESP32 GND   (common ground — required)

ESP32 GPIO 16 ── 330 Ω ── [optional 74AHCT125 3.3→5 V] ── strip D
strip R: leave open for first test; if the datasheet is GS8208/WS2815, tie R to D at the input
```

On a wall brick with USB-powered ESP32, omit the buck; still tie brick − to ESP32 GND.

### Do / don’t

| Do | Don’t |
|----|--------|
| Common GND: 24 V −, strip `G`, ESP32 GND (and buck − if used) | Feed the strip from ESP32 `5V` / `3V3` |
| Fuse on battery +; optional on a UL wall brick | Connect 24 V to `D`, `R`, or any MCU pin |
| 330 Ω in series on data, short wire to strip `D` | Share this ESP32 with the 768-LED PAB matrix |
| Cap at the strip input (1000 µF, **35 V+**) | Skip isolation and put 24 V on Zero/ESP32 VIN |

Level shifter: many 24 V pixels still want **5 V data**. If colors glitch or only the first pixel works, add a **74AHCT125** powered at **5 V** (same buck). Short pigtail + 330 Ω is enough to try without it.

---

## Circuit (type B — analog RGB)

Common-anode 24 V: `+24V` stays at 24 V. `G`, `R`, `D` are **switched to ground** with logic-level N-MOSFETs.

```text
strip +24V ← 24 V fused
strip G  → MOSFET1 drain   source → GND   gate ← 100 Ω ← ESP32 GPIO 17
strip R  → MOSFET2 drain   source → GND   gate ← 100 Ω ← ESP32 GPIO 18
strip D  → MOSFET3 drain   source → GND   gate ← 100 Ω ← ESP32 GPIO 16
each gate 10 kΩ to GND
```

Use **logic-level** FETs that are fully on at 3.3 V gate (AO3400, IRLZ44N, IRLZ34). PWM with the analog mode in the sketch. **No** NeoPixel library on those pins.

---

## BOM

| Qty | Part | Why |
|-----|------|-----|
| 1 | ESP32 DevKit (you have) | MCU |
| 1 | **Original 24 V DC brick** (or battery pack if cordless) | Strip rail |
| 1 | USB 5 V charger for ESP32 **or** mini buck **24 V → 5 V**, ≥ 2 A | MCU |
| 1 | Fuse holder + fuse (3 A) | Required on a pack; optional on a wall brick |
| 1 | Power switch | On/off (handy on a pack; brick can be unplugged) |
| 1 | 1000 µF 35 V electrolytic | Strip input bulk |
| 1 | 330 Ω ¼ W | Data series |
| 1 | MAX9814 mic module | Beat envelope into ADC |
| 1 | 74AHCT125 (optional) | 3.3 V → 5 V data |
| 3 | Logic-level N-MOSFET + 100 Ω + 10 kΩ (only if type B) | Analog RGB |

---

## Firmware

### Custom sketch (this repo)

[`beat_reactive/beat_reactive.ino`](beat_reactive/beat_reactive.ino)

1. Set `LED_COUNT` (start with `20` per meter if type A / WS2811-24V; use `60` per meter if one IC per LED).
2. Set `STRIP_MODE` to `MODE_DIGITAL` or `MODE_ANALOG`.
3. Board: **esp32:esp32:esp32**. LED **GPIO 16**, mic **GPIO 34**.
4. Upload, open Serial at 115200. Clap / play a kick: envelope and `BEAT` lines should print; strip should flash then decay.

Libraries: **Adafruit NeoPixel** (digital mode only).

### How the ESP32 hears a beat

The MCU does **not** decode songs or Bluetooth audio. A microphone turns air pressure into voltage; the ESP32 measures that voltage and looks for a **sudden loudness jump** (kick, clap, snare).

```text
MAX9814 mic OUT ── GPIO 34 (ADC, 12-bit)

every 8 ms:
  48 analog reads → average
  subtract the ~1.65 V DC bias  →  "how loud right now"
  fast-rise / slow-fall envelope
  slow baseline of room level
  if envelope > 1.45 × baseline  and  ≥140 ms since last hit
       → BEAT: flash strip, step hue
  else
       → brightness decays; a little leftover glow follows the envelope
```

That is **time-domain onset detection**, not an FFT. It is good at drums and claps. Sustained pads or quiet music will look like a dim pulse, not a flash. The MAX9814 already AGC-amplifies the mic; GPIO 34 is input-only ADC (do not use 16 for the mic).

Serial prints `BEAT env=… base=…` so you can tune `BEAT_RATIO` (higher = fewer false flashes) and `REFRACTORY_MS` (minimum time between flashes).

**WLED Audio Reactive** is the other path: an I2S mic (INMP441) and an FFT into bass/mid/treble. Use that if you want spectrum bars, not just a kick flash.

### Tap Raspberry-PAB audio (instead of a room mic)

Yes — but only if you can get an **analog copy** of what PipeWire is playing. The kiosk does not have a line-out pin on the ESP32 matrix board. Playback is [Bluetooth A2DP, else HDMI](../../docs/bluetooth-audio.md).

| PAB sink | Can you tap it electrically? |
|----------|------------------------------|
| **Bluetooth speaker** | **No.** A2DP leaves the Pi as radio. Put the MAX9814 next to the speaker, or duplicate audio to analog (below). |
| **HDMI** (TV / monitor speakers) | Not on the HDMI cable. Use an **HDMI audio extractor** (HDMI in → HDMI out + 3.5 mm), then the line-level circuit. |
| **Pi 4 3.5 mm jack** (or USB DAC) | **Yes.** Route playback there (or to a combine sink) and wire the jack to GPIO 34. Pi 5 has **no** analog jack; use a USB DAC. |

The beat sketch already assumes a ~1.65 V bias, so a line-level tap with a bias network can replace the MAX9814. Same GPIO **34**, same code.

#### Line-level into GPIO 34

Speaker-level / amp output will blow the ADC. Use **line out** only (~1 Vrms).

```text
3.5 mm tip (L)  ── 10 kΩ ──┐
3.5 mm ring (R) ── 10 kΩ ──┼── 4.7 µF ──┬── GPIO 34
3.5 mm sleeve ──────────── GND          │
ESP32 3V3 ── 100 kΩ ────────────────────┤   (bias ~1.65 V)
GPIO 34 ── 100 kΩ ──────────────────── GND
optional 3.3 V schottky clamp on GPIO 34
Pi GND ── ESP32 GND
```

Keep the 24 V LED ground common with ESP32; tie Pi GND only through this audio GND, not through the 24 V pack.

#### Bluetooth and analog at once

If the field speaker is Bluetooth and you still want a wire tap, PipeWire must **duplicate** the stream (combine sink / loopback) to the 3.5 mm or USB DAC. The kiosk today prefers BT and does **not** do that by default. Acoustic mic next to the speaker is simpler.

A software tap (Pi reads the PipeWire monitor, detects beats, sends `BEAT` over serial) would follow Bluetooth too, but that is a kiosk firmware change — not this standalone sketch.

### WLED (optional, fancier)

Flash [WLED](https://install.wled.me/) with Audio Reactive. LED pin **16**, 24 V strip still powered as above. Digital mic (INMP441) is more reliable than analog in WLED. Use the phone UI for palettes; this is the path if you want lots of effects without editing C++.

---

## Checklist

- [ ] Confirmed `G` is ground; 24 V only on `+24V`
- [ ] Brick is **24 V DC** (or fuse + switch on battery +)
- [ ] ESP32 from USB **or** buck 5.1 V; **not both**; common GND to strip `G`
- [ ] 1000 µF at strip input
- [ ] GPIO 16 → 330 Ω → `D` (digital) **or** three MOSFETs (analog)
- [ ] `LED_COUNT` / `STRIP_MODE` set; brightness ≤ 80
- [ ] Smoke test: red wipe, then beats on a kick drum / clap

## Troubleshooting

| Symptom | Check |
|---------|--------|
| MCU boots, strip dark | Mode A vs B; `LED_COUNT`; data on `D` not `R`; try 5 V level shift |
| First pixel wrong color / stuck | Level shift; 330 Ω; common GND |
| Beats missed or always-on | `MIC_GAIN` / `BEAT_RATIO`; MAX9814 gain jumper; keep mic off the buck |
| ESP32 brownout | Buck current ≥ 2 A; don’t power strip from ESP32 |
| Strip voltage sag / dim end | Inject 24 V at far end; shorter run or thicker wire |
