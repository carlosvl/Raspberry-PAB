# ESP32 wiring (3-panel matrix + buzzer)

Production MCU for Raspberry-PAB: **38-pin ESP32-WROOM-32** DevKit (USB-C, **CP2102**) on an AITRIP-style screw-terminal breakout.

- Firmware: [`raspberry_pab_hardware/`](raspberry_pab_hardware/) — buzzer **GPIO 4** + matrix **GPIO 16**, **768 LEDs** (8×96)
- Smoke test: [`matrix_test/`](matrix_test/)
- Upload: `scripts/upload-esp32-hardware.sh`, `scripts/upload-esp32-matrix-test.sh`
- Field power: [`../power/MOBILE-POWER.md`](../power/MOBILE-POWER.md)
- Legacy Nano (2 panels): [`../arduino/`](../arduino/)

---

## Pin map (screw terminals)

| Signal | Terminal label | ESP32 GPIO | Notes |
|--------|----------------|------------|--------|
| WS2812 DIN | **16** | GPIO **16** | 330 Ω series → panel1 DIN |
| Buzzer I/O | **4** | GPIO **4** | Active buzzer, **low-level** trigger (LOW = beep) |
| Buzzer VCC | **5V** or **3V3** | — | Prefer module **5V** from breakout `5V` if the module needs 5 V; GND common |
| Buzzer GND | **GND** | GND | Common with LED rail |
| Common GND | any **GND** | GND | Must tie to Cywhrvzsf **VO−** / panel GND |
| Matrix 5 V | *(not ESP32)* | — | From Cywhrvzsf **5.1 V** only |

ESP32 is powered by **Pi USB-C** (data + 5 V for the DevKit). **Never** power 768 LEDs from the ESP32 `5V` pin.

---

## Three-panel daisy-chain

Logical display: **8×96** = three 8×32 panels, **768** LEDs.

```text
Pi USB-C ──► ESP32 DevKit
               GPIO 16 ──[330 Ω]──► panel1 DIN
               GPIO 4  ───────────► buzzer I/O
               GND ──── common GND

Cywhrvzsf 5.1 V ──► panel1 5V + center inject
                 ──► panel2 5V + center inject
                 ──► panel3 5V + center inject
                 ──► all panel GNDs + ESP32 GND

panel1 DOUT ──► panel2 DIN
panel2 DOUT ──► panel3 DIN
```

| Panel | DIN from | Power |
|-------|----------|--------|
| 1 (closest to ESP32) | GPIO 16 via 330 Ω | Inject 5V/GND at input **and** center pads |
| 2 | Panel 1 **DOUT** | Same rail + inject |
| 3 | Panel 2 **DOUT** | Same rail + inject |

Add **1000 µF ≥16 V** across 5V/GND near each panel inject (+ to 5 V, − to GND).

---

## Serial / Pi `.env`

Same USB port for buzzer + matrix (combined firmware):

```bash
PAB_BUZZER_ENABLED=true
PAB_BUZZER_PORT=/dev/serial/by-id/usb-Silicon_Labs_CP210*-if00-port0   # or auto-detect
PAB_MATRIX_ENABLED=true
PAB_MATRIX_PORT=          # empty → uses buzzer port
PAB_MATRIX_WIDTH=96
PAB_MATRIX_BRIGHTNESS=64  # field: keep ≤128
```

Upload:

```bash
PAB_BUZZER_PORT=/dev/ttyUSB0 ./scripts/upload-esp32-matrix-test.sh   # wiring check
PAB_BUZZER_PORT=/dev/ttyUSB0 ./scripts/upload-esp32-hardware.sh      # production
```

Expect boot: `READY PIXELS 768 FREE <large>`.

---

## 3.3 V data into 5 V WS2812

ESP32 GPIO is **3.3 V**. Short DIN wire + 330 Ω usually works. If panels stay dark or glitch:

- Shorten the data wire
- Confirm common GND
- Add a **74AHCT125** (5 V powered) level shifter on DIN (ESP32 → buffer → panel1 DIN)

---

## Buzzer note

Active **low-level** modules: I/O LOW = on. ESP32 GPIO 4 at 3.3 V LOW is usually enough. If the buzzer never sounds, drive I/O with an NPN/MOSFET to pull the module input to GND while keeping VCC at 5 V.

---

## Checklist

- [ ] GPIO 16 → 330 Ω → panel1 DIN; DOUT→DIN through all three panels
- [ ] GPIO 4 → buzzer I/O; buzzer VCC/GND correct
- [ ] All three panels have 5V/GND inject + 1000 µF
- [ ] ESP32 GND ↔ LED rail GND
- [ ] Matrix **not** powered from ESP32 `5V`
- [ ] `matrix_test` lights panels 1→2→3; production `PIXELS 768`
- [ ] Admin Test matrix + Test buzzer on the same USB-C port
