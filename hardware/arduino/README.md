# Arduino Nano + buzzer (Raspberry-PAB)

Hardware test sketch for a **low-level-trigger** active buzzer on **D3**.

## Wiring

| Buzzer | Nano |
|--------|------|
| VCC    | 5V   |
| GND    | GND  |
| I/O    | D3   |

## Mac setup

```bash
brew install arduino-cli
arduino-cli core update-index
arduino-cli core install arduino:avr
```

For GUI editing, install [Arduino IDE](https://www.arduino.cc/en/software) (`brew install --cask arduino-ide`).

Board settings for this USB-serial Nano clone:

- **Board:** Arduino Nano
- **Processor:** ATmega328P (Old Bootloader)
- **Port:** `/dev/cu.usbserial-110` (CH340; your port name may differ)

## Compile and upload

```bash
FQBN="arduino:avr:nano:cpu=atmega328old"
SKETCH="hardware/arduino/buzzer_test"
PORT="/dev/cu.usbserial-110"

arduino-cli compile --fqbn "$FQBN" "$SKETCH"
arduino-cli upload -p "$PORT" --fqbn "$FQBN" "$SKETCH"
```

After upload, the buzzer should beep for 300 ms every second.

## Serial monitor

```bash
arduino-cli monitor -p /dev/cu.usbserial-110 -c baudrate=9600
```

Expect `beep` lines once per second.

## Production buzzer firmware

Sketch: `hardware/arduino/raspberry_pab_buzzer/raspberry_pab_buzzer.ino`

Upload:

```bash
PAB_BUZZER_PORT=/dev/cu.usbserial-110 ./scripts/upload-buzzer.sh
```

On the Pi, set in `.env`:

```bash
PAB_BUZZER_ENABLED=true
PAB_BUZZER_PORT=/dev/serial/by-id/usb-Serial_*-if00
PAB_BUZZER_MODE=active   # or passive for piezo
PAB_BUZZER_BAUD=115200
```

Ensure the `pi` user is in the `dialout` group.

### Wiring

**Active module (low-level trigger):**

| Buzzer | Nano |
|--------|------|
| VCC | 5V |
| GND | GND |
| I/O | D3 |

**Passive piezo:** + to D3, − to GND. Set `PAB_BUZZER_MODE=passive` for pitch control.

### Per-rule settings

In `/admin`, each reminder rule can enable **Play buzzer** and set pitch (Hz), volume (0–100), count, beep length, and gap.
