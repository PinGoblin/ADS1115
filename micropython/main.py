"""ESP32 MicroPython example: a thermistor on CH0 and voltages on CH1–CH3.

Prints the temperature and three voltages once a second. Copy `ads1115.py` and this
file to the ESP32, then reset it.

**Wiring** (ESP32 DevKit defaults; change the pins below for other boards)

| PinGoblin ADS1115 J1 | ESP32 |
|---|---|
| VDD (Required) | 3V3 |
| GND (Required) | GND |
| SCL (Required) | GPIO22 |
| SDA (Required) | GPIO21 |

**Board setup**

- CH0 (J2): 10 kΩ NTC thermistor on the SIG and GND pins, RES jumper JP5 closed.
- CH1–CH3 (J3–J5): Voltage-output sensors, RES open.

Run `micropython main.py --mock` on a computer with the MicroPython Unix port to try it
without hardware.
"""
import math
import sys
import time

from ads1115 import ADS1115, BusError, InputRangeError, MockI2C

VDD = 3.30            # measure your board's real VDD (TP5 to TP6)
R_EXC = 10_000        # excitation resistor fitted on the board
R0, T0_C, BETA = 10_000, 25.0, 3950   # thermistor datasheet values
R_OPEN = 5_000_000    # above this the thermistor is treated as disconnected

if "--mock" in sys.argv:
    i2c = MockI2C()   # a simulated board, no hardware
else:
    from machine import I2C, Pin
    # 100 kHz suits the board's 10 kΩ pull-ups; use 400 kHz only with 2.2-4.7 kΩ pull-ups added
    i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=100_000)
found = i2c.scan()
print("I2C devices:", [hex(a) for a in found])
if 0x48 not in found:
    raise SystemExit("No board found at 0x48: Check the wiring and the address jumpers")

adc = ADS1115(i2c, address=0x48, fsr=4.096, rate=128)


def ntc_celsius(v):
    """Convert the CH0 voltage to °C (Beta equation), or `None` for an open or short circuit."""
    if v <= 0 or v >= VDD:
        return None
    r = R_EXC * v / (VDD - v)
    if r > R_OPEN:
        return None
    return 1 / (1 / (T0_C + 273.15) + math.log(r / R0) / BETA) - 273.15


def read(ch):
    """One channel in volts, or `None` (with the reason printed) if it is beyond the range."""
    try:
        return adc.read_voltage(ch, samples=4)
    except InputRangeError as exc:
        print(exc)
        return None


while True:
    try:
        v = [read(ch) for ch in range(4)]
    except BusError as exc:
        raise SystemExit(exc)
    t = None if v[0] is None else ntc_celsius(v[0])
    t_txt = "--.-" if t is None else "%.2f" % t
    v_txt = ["over" if x is None else "%.3f" % x for x in v[1:]]
    print("T=%s C   CH1=%s V  CH2=%s V  CH3=%s V" % (t_txt, v_txt[0], v_txt[1], v_txt[2]))
    time.sleep(1)
