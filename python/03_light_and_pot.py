#!/usr/bin/env python3
"""Example 3: two sensor types on one board.

Shows how a voltage-output channel and a resistive channel are converted differently.

**Board setup**

| Channel | Sensor | RES jumper | Wiring |
|---|---|---|---|
| CH0 (J2) | Potentiometer | Open | Ends to GND and VDD, wiper to SIG |
| CH1 (J3) | Bare LDR | Closed (JP6) | One lead to SIG, the other to GND |
"""
import time

from pingoblin_ads1115 import ADS1115, resistance_from_voltage, percent_of_range

VDD = 3.30

adc = ADS1115(fsr=4.096)
POT, LDR = 0, 1        # channels

try:
    while True:
        v_pot = adc.read_voltage(POT, samples=8)
        pot_pct = percent_of_range(v_pot, 0.0, VDD)

        v_ldr = adc.read_voltage(LDR, samples=8)
        r_ldr = resistance_from_voltage(v_ldr, VDD)
        # LDR resistance falls as light rises; dark ~1 M, bright ~1 k.
        # Brightness is shown as % of the voltage swing (bright = low voltage).
        light_pct = 100.0 - percent_of_range(v_ldr, 0.0, VDD)

        r_txt = "open" if r_ldr == float("inf") else f"{r_ldr/1000:8.1f} k"
        print(f"Pot {pot_pct:5.1f} %   |   LDR {r_txt}  light {light_pct:5.1f} %")
        time.sleep(0.25)
except KeyboardInterrupt:
    pass
