# Cywhrvzsf 600W buck setup (12 V → 5.1 V for LEDs)

Precise setup for the [Cywhrvzsf 600W 25A CC/CV step-down](https://a.co/d/087sPZJu) when the source is a **12 V** battery or [BLUETTI AC2A](https://www.bluettipower.com/products/solar-generator-ac2a) car outlet, and the load is the WS2812 **LED 5 V** rail.

See also: [MOBILE-POWER.md](MOBILE-POWER.md).

---

## What you adjust (and what you don’t)


| Adjustment               | Control              | Your setting                     |
| ------------------------ | -------------------- | -------------------------------- |
| **Input voltage**        | *(none — no pot)*    | Fixed by source ≈ **12 V**       |
| **Output voltage**       | **VIADJ** (blue pot) | **~5.1 V**                       |
| **Output current limit** | **IADJ** (blue pot)  | **~18–20 A** (or full CW + fuse) |


There is **no input-voltage adjustment** on this board. Vin is whatever the battery/AC2A puts out.

---



## Module constraints (from the product)

- Input: **12–75 V**
- Output: **2.5–60 V** adjustable (step-down only)
- Practical max Vout ≈ **0.8 × Vin** → at 12 V in, max ≈ **9.6 V** (5.1 V is fine)
- Current: **1–25 A** adjustable; continuous up to ~25 A / ~500 W
- **Step-down only:** Vin must be **higher** than Vout
- **No reverse-polarity protection** on input
- **Low-side current sense:** do **not** short **−IN** to **−OUT** with a wire
- Long high-power runs need heatsinking

---



## Before you start

- **No LED panels connected** until voltage is set and verified
- Multimeter (DC volts; amps optional)
- Flat-head screwdriver for the pots
- Power source: **12 V** (AC2A car outlet or 12 V battery)
- Polarity: **+IN** ← 12 V +, **−IN** ← 12 V −

---



## Step 1 — Wire input only

1. Connect **12 V + → +IN**, **12 V − → −IN**.
2. Leave **VO+ / VO−** open (or meter only).
3. Turn the source on.

---



## Step 2 — Set output voltage (VIADJ)

1. Multimeter on **DC volts**.
2. Probes: **red → VO+**, **black → VO−**.
3. Adjust **VIADJ**:
  - **Clockwise** = raise voltage
  - **Counterclockwise** = lower voltage
4. Aim for **5.05–5.15 V** (target **~5.10 V**).
5. If the meter shows **~0 V**, **IADJ** is likely at minimum — raise current slightly (Step 3), then finish voltage.

Do **not** connect panels until VO reads ~5.1 V.

---



## Step 3 — Set current limit (IADJ)

Goal: limit high enough that normal LED load never enters constant-current (CC) mode (that causes sag/flicker). Target **~18–20 A**. Use a **fuse** on the 5 V rail for faults.

### Recommended (no dead-short)

1. With Vout ≈ 5.1 V, turn **IADJ clockwise** many turns (to stop, or well past mid + several turns).
2. That places the limit near the high end. Good for CV LED use with a fuse.



### Vendor method (exact amps — be careful)

1. Confirm unloaded output ≈ **5 V**.
2. Turn **IADJ counterclockwise ~10 turns** (output may go to ~0 A / blank — normal).
3. Multimeter on **10 A or 20 A** range (correct jack).
4. Briefly put the meter **across VO+ and VO−** as a short on the amps range — **only a second or two** while adjusting.
5. Turn **IADJ clockwise** until the meter shows **~18–20 A**.
6. Remove the short immediately.
7. Recheck open-circuit voltage is still **~5.1 V**; tweak **VIADJ** if needed.

Prefer “IADJ high + fuse” over the short method if you are unsure.

---



## Step 4 — Verify, then connect LEDs

1. Power on, no panels: **VO+ to VO− ≈ 5.1 V**.
2. Power off.
3. Connect panels: **VO+ → panel 5 V**, **VO− → panel GND** (and center injects).
4. Add **1000 µF ≥16 V** at each panel inject (+ to 5 V, − to GND).
5. Optional: **330 Ω** in series on **Nano D6 → panel1 DIN**.
6. Nano/Pi GND → **VO−** only (not a Vin−↔Vout− jumper).
7. Power on; recheck **~5.0–5.2 V at the panel** under a normal scroll/test.

---



## Do / don’t


| Do                                     | Don’t                                 |
| -------------------------------------- | ------------------------------------- |
| Set voltage with **no LEDs** attached  | Guess Vout with panels already wired  |
| Fuse the 5 V LED rail (~15–20 A)       | Reverse +/− on the input              |
| Heatsink for long runs                 | Short **−IN** to **−OUT**             |
| Keep Vin > Vout (12 → 5.1 is OK)       | Expect boost — this module only bucks |
| Power LED rail from AC2A **12 V** only | Feed matrices from Pi USB or Nano 5 V |


---



## Quick checklist

- [ ] Source is **12 V**, polarity correct on +IN / −IN
- [ ] **VIADJ** set to **~5.1 V** with no panels
- [ ] **IADJ** high (~18–20 A or full CW)
- [ ] 5 V rail fused
- [ ] Panels + caps connected; GND at **VO−** only
- [ ] Voltage rechecked under load (~5.0–5.2 V at panel)