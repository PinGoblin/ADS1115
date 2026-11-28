#!/usr/bin/env python3
"""Example 4: several boards on one I²C bus, up to 16 channels.

Finds every board at 0x48–0x4B and prints all their channels once a second.

**Board setup**

Give every board a different address with the solder jumpers:

| Board | Jumpers | Address |
|---|---|---|
| A | JP1 closed (default) | 0x48 |
| B | Cut JP1, close JP2 | 0x49 |
| C | Cut JP1, close JP3 | 0x4A |
| D | Cut JP1, close JP4 | 0x4B |

Wire pins 1–4 of every board's J1 (VDD, GND, SCL, SDA) in parallel to the Pi.
`i2cdetect -y 1` lists the addresses the Pi can see. Up to four boards can share the Pi's bus.
"""
import time

from pingoblin_ads1115 import find_boards

boards = find_boards(fsr=4.096)          # tries 0x48-0x4B on I2C bus 1
for addr in boards:
    print(f"Found board at 0x{addr:02X}")

if not boards:
    raise SystemExit("No boards found - check wiring, power and `i2cdetect -y 1`.")

try:
    while True:
        line = []
        for addr, adc in boards.items():
            volts = " ".join(f"{adc.read_voltage(ch):5.3f}" for ch in range(4))
            line.append(f"0x{addr:02X}: {volts}")
        print("  |  ".join(line))
        time.sleep(1)
except KeyboardInterrupt:
    pass
