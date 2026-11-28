#!/usr/bin/env python3
"""Example 6: one-point gain calibration.

Removes the small gain error caused by the 4.7 kΩ series resistor and the ADC's own
tolerance (typically 0.1–0.2 %).

1. Leave the channel's RES jumper open.
2. Link the header's VDD pin to its SIG pin with a jumper wire, or apply any steady
   voltage between 1 V and VDD.
3. Measure that voltage at the header with a good multimeter.
4. Run `python3 06_calibrate.py <channel> <multimeter volts>`,
   for example `python3 06_calibrate.py 0 3.297`.

The factor is saved to `calibration.json` and applied automatically by the other
examples. Repeat for each channel you use.

Run with `--mock` to try it without hardware.
"""
import sys

from pingoblin_ads1115 import (ADS1115, BusError, InputRangeError, MockBus, load_calibration,
                               save_calibration)

args = [a for a in sys.argv[1:] if a != "--mock"]
if len(args) != 2:
    raise SystemExit(__doc__)

ch = int(args[0])
true_v = float(args[1])
if ch not in range(4) or not 0.5 <= true_v <= 5.5:
    raise SystemExit("Channel must be 0-3 and voltage 0.5-5.5 V")

bus = MockBus() if "--mock" in sys.argv else 1   # --mock: a simulated board, no hardware
adc = ADS1115(bus, fsr=4.096, rate=8)            # slowest rate = lowest noise
try:
    measured = adc.read_voltage(ch, samples=32)
except (BusError, InputRangeError) as exc:
    raise SystemExit(exc)
if measured < 0.25:
    raise SystemExit(f"CH{ch} reads {measured:.4f} V: Check the voltage is connected")

factor = true_v / measured
if not 0.97 <= factor <= 1.03:
    raise SystemExit(f"Factor {factor:.5f} is outside ±3 %: Check the wiring and the meter")

cal = load_calibration()
cal[str(ch)] = round(factor, 6)
save_calibration(cal)
print(f"CH{ch}: Measured {measured:.5f} V, true {true_v:.5f} V, factor {factor:.5f} saved")
