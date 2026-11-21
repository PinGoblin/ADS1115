#!/usr/bin/env python3
"""
Example 1 - Read all four channels.

Wiring: host to J1 or a Qwiic connector, sensors to J2-J5 (GND, VDD, SIG).
All RES jumpers open (factory default) = voltage-output sensors.

Prints raw counts and volts for CH0-CH3 twice a second. Ctrl+C to stop.
"""
import time

from breakout_ads import open_adc, channel, load_calibration, apply_calibration

ads = open_adc(address=0x48, gain=1)          # gain 1 = +/-4.096 V full scale
chans = [channel(ads, ch) for ch in range(4)]
cal = load_calibration()                       # optional, see 06_calibrate.py

print("CH0 (J2)        CH1 (J3)        CH2 (J4)        CH3 (J5)")
try:
    while True:
        cells = []
        for ch, c in enumerate(chans):
            volts = apply_calibration(c.voltage, ch, cal)
            cells.append(f"{c.value:6d} {volts:6.3f}V")
        print("  ".join(cells))
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
