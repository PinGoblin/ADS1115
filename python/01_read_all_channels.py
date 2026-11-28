#!/usr/bin/env python3
"""Example 1: read all four channels.

Prints the raw count and voltage of CH0–CH3 twice a second. Press Ctrl+C to stop.

**Board setup**

- Host on J1.
- Voltage-output sensors on J2–J5 (GND, VDD, SIG).
- All RES jumpers open (the factory default).

Applies the calibration from `06_calibrate.py` if `calibration.json` exists.
"""
import time

from pingoblin_ads1115 import ADS1115, load_calibration, apply_calibration

adc = ADS1115(address=0x48, fsr=4.096)         # +/-4.096 V full scale, 128 samples/s
cal = load_calibration()                       # optional, see 06_calibrate.py

print("CH0 (J2)        CH1 (J3)        CH2 (J4)        CH3 (J5)")
try:
    while True:
        cells = []
        for ch in range(4):
            raw = adc.read_raw(ch)
            volts = apply_calibration(raw * adc.fsr / 32768, ch, cal)
            cells.append(f"{raw:6d} {volts:6.3f}V")
        print("  ".join(cells))
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
