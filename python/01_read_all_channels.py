#!/usr/bin/env python3
"""Example 1: read all four channels.

Prints the raw count and voltage of CH0–CH3 twice a second. Press Ctrl+C to stop.

**Board setup**

- Host on J1.
- Voltage-output sensors on J2–J5 (GND, VDD, SIG).
- All RES jumpers open (the factory default).

Applies the calibration from `06_calibrate.py` if `calibration.json` exists.

Run with `--mock` to try it without hardware.
"""
import sys
import time

from pingoblin_ads1115 import ADS1115, BusError, MockBus, apply_calibration, load_calibration

bus = MockBus() if "--mock" in sys.argv else 1   # --mock: a simulated board, no hardware
adc = ADS1115(bus, address=0x48, fsr=4.096)    # ±4.096 V full scale, 128 samples/s
cal = load_calibration()                       # optional, see 06_calibrate.py

print("CH0 (J2)        CH1 (J3)        CH2 (J4)        CH3 (J5)")
try:
    while True:
        cells = []
        for ch in range(4):
            raw = adc.read_raw(ch)
            if raw in (32767, -32768):
                cells.append(f"{raw:6d} over range")
            else:
                volts = apply_calibration(raw * adc.fsr / 32768, ch, cal)
                cells.append(f"{raw:6d} {volts:6.3f}V")
        print("  ".join(cells))
        time.sleep(0.5)
except BusError as exc:
    raise SystemExit(exc)
except KeyboardInterrupt:
    pass
