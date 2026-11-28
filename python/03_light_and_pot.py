#!/usr/bin/env python3
"""Example 3: two sensor types on one board.

Shows how a voltage-output channel and a resistive channel are converted differently.

**Board setup**

| Channel | Sensor | RES jumper | Wiring |
|---|---|---|---|
| CH0 (J2) | Potentiometer | Open | Ends to GND and VDD, wiper to SIG |
| CH1 (J3) | Bare LDR | Closed (JP6) | One lead to SIG, the other to GND |

Run with `--mock` to try it without hardware.
"""
import sys
import time

from pingoblin_ads1115 import (ADS1115, BusError, InputRangeError, MockBus, percent_of_range,
                               resistance_from_voltage)

VDD = 3.30

bus = MockBus() if "--mock" in sys.argv else 1   # --mock: a simulated board, no hardware
adc = ADS1115(bus, fsr=4.096)
POT, LDR = 0, 1        # channels

try:
    while True:
        try:
            v_pot = adc.read_voltage(POT, samples=8)
            v_ldr = adc.read_voltage(LDR, samples=8)
        except InputRangeError as exc:
            print(exc)
        else:
            pot_pct = percent_of_range(v_pot, 0.0, VDD)
            r_ldr = resistance_from_voltage(v_ldr, VDD)
            # LDR resistance falls as light rises; dark 1 M, bright 1 k.
            # Brightness is shown as % of the voltage swing (bright = low voltage).
            light_pct = 100.0 - percent_of_range(v_ldr, 0.0, VDD)
            r_txt = "open" if r_ldr == float("inf") else f"{r_ldr/1000:8.1f} k"
            print(f"Pot {pot_pct:5.1f} %   |   LDR {r_txt}  light {light_pct:5.1f} %")
        time.sleep(0.25)
except BusError as exc:
    raise SystemExit(exc)
except KeyboardInterrupt:
    pass
