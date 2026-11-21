#!/usr/bin/env python3
"""
Example 3 - Mixing sensor types on one board.

  CH0 (J2): potentiometer, RES open.  Pot ends to GND and VDD pins, wiper to SIG.
  CH1 (J3): bare LDR (light-dependent resistor), RES closed (JP6).
            One lead to SIG, the other to GND.

Shows how each channel is converted differently.
"""
import time

from breakout_ads import open_adc, channel, read_average, resistance_from_voltage, percent_of_range

VDD = 3.30

ads = open_adc(gain=1)
pot = channel(ads, 0)
ldr = channel(ads, 1)

try:
    while True:
        v_pot = read_average(pot)
        pot_pct = percent_of_range(v_pot, 0.0, VDD)

        v_ldr = read_average(ldr)
        r_ldr = resistance_from_voltage(v_ldr, VDD)
        # LDR resistance falls as light rises; dark ~1 M, bright ~1 k.
        # Brightness is shown as % of the voltage swing (bright = low voltage).
        light_pct = 100.0 - percent_of_range(v_ldr, 0.0, VDD)

        r_txt = "open" if r_ldr == float("inf") else f"{r_ldr/1000:8.1f} k"
        print(f"Pot {pot_pct:5.1f} %   |   LDR {r_txt}  light {light_pct:5.1f} %")
        time.sleep(0.25)
except KeyboardInterrupt:
    pass
