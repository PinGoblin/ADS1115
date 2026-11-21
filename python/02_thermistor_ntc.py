#!/usr/bin/env python3
"""Example 2: temperature from a 10 kΩ NTC thermistor.

**Board setup**

- Close the RES jumper of the channel you use (JP5 for CH0).
- Connect one thermistor lead to SIG (pin 3) and the other to GND (pin 1) of J2.
  The VDD pin is not used, and a thermistor has no polarity.

**Accuracy tips**

- Measure the board's real VDD between TP5 and TP6 and set `VDD`, or
- set `VDD_CHANNEL` to a spare channel and link that header's VDD pin to its SIG pin with
  a jumper wire (RES open). The script then measures VDD live.
- Set `R0`, `T0_C` and `BETA` from your thermistor's datasheet.
"""
import time

from breakout_ads import (open_adc, channel, read_average, resistance_from_voltage,
                          ntc_celsius, load_calibration, apply_calibration)

NTC_CHANNEL = 0        # CH0 = J2, RES jumper JP5 closed
VDD = 3.30             # your measured supply voltage
VDD_CHANNEL = None     # e.g. 3 to measure VDD live on CH3 (J5 VDD linked to SIG)

# Thermistor datasheet values
R0 = 10_000.0          # resistance at T0
T0_C = 25.0
BETA = 3950.0          # check your part: 3380, 3435 and 3950 are all common

R_OPEN = 5_000_000     # above this the thermistor is treated as disconnected (a 10 k NTC is ~1 M at -55 C)

ads = open_adc(gain=1)
ntc = channel(ads, NTC_CHANNEL)
vdd_ch = channel(ads, VDD_CHANNEL) if VDD_CHANNEL is not None else None
cal = load_calibration()

try:
    while True:
        vdd = VDD
        if vdd_ch is not None:
            vdd = apply_calibration(read_average(vdd_ch), VDD_CHANNEL, cal)
        v = apply_calibration(read_average(ntc, samples=16), NTC_CHANNEL, cal)
        r = resistance_from_voltage(v, vdd)
        if r > R_OPEN:
            print("Open circuit - is the thermistor connected and RES closed?")
        elif r < 50:
            print("Short circuit - check the thermistor wiring")
        else:
            t = ntc_celsius(r, R0, T0_C, BETA)
            print(f"V={v:.4f} V  VDD={vdd:.3f} V  R={r/1000:7.3f} k  T={t:6.2f} C")
        time.sleep(1)
except KeyboardInterrupt:
    pass
