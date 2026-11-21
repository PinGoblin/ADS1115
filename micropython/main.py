"""ESP32 MicroPython example: a thermistor on CH0 and voltages on CH1–CH3.

Prints the temperature and three voltages once a second. Copy `ads1115.py` and this
file to the ESP32, then reset it.

**Wiring** (ESP32 DevKit defaults; change the pins below for other boards)

| Breakout J1 | ESP32 |
|---|---|
| VDD | 3V3 |
| GND | GND |
| SCL | GPIO22 |
| SDA | GPIO21 |

Or use a Qwiic cable if your ESP32 board has a Qwiic / STEMMA QT port.

**Board setup**

- CH0 (J2): 10 kΩ NTC thermistor on the SIG and GND pins, RES jumper JP5 closed.
- CH1–CH3 (J3–J5): voltage-output sensors, RES open.
"""
import math
import time
from machine import I2C, Pin

from ads1115 import ADS1115

VDD = 3.30            # measure your board's real VDD (TP5 to TP6)
R_EXC = 10_000        # excitation resistor fitted on the board
R0, T0_C, BETA = 10_000, 25.0, 3950   # thermistor datasheet values

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400_000)
found = i2c.scan()
print("I2C devices:", [hex(a) for a in found])
if 0x48 not in found:
    raise SystemExit("ADS1115 not found at 0x48 - check wiring and the address jumpers")

adc = ADS1115(i2c, address=0x48, fsr=4.096, rate=128)


def ntc_celsius(v):
    """Convert the CH0 voltage to °C (Beta equation), or `None` for an open or short circuit."""
    if v <= 0 or v >= VDD:
        return None
    r = R_EXC * v / (VDD - v)
    return 1 / (1 / (T0_C + 273.15) + math.log(r / R0) / BETA) - 273.15


while True:
    v = [adc.read_voltage(ch, samples=4) for ch in range(4)]
    t = ntc_celsius(v[0])
    t_txt = "--.-" if t is None else "%.2f" % t
    print("T=%s C   CH1=%.3f V  CH2=%.3f V  CH3=%.3f V" % (t_txt, v[1], v[2], v[3]))
    time.sleep(1)
