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

Wire pins 1–4 of every board's J1 (GND, VDD, SCL, SDA) in parallel to the Pi.
`i2cdetect -y 1` lists the addresses the Pi can see. Up to four boards can share the Pi's bus.

Run with `--mock` to try it without hardware.
"""
import sys
import time

from pingoblin_ads1115 import BusError, InputRangeError, MockBus, find_boards

# --mock: two simulated boards at 0x48 and 0x49, no hardware
bus = MockBus(addresses=(0x48, 0x49)) if "--mock" in sys.argv else 1
boards = find_boards(bus, fsr=4.096)     # tries 0x48-0x4B
for addr in boards:
    print(f"Found board at 0x{addr:02X}")

if not boards:
    raise SystemExit("No boards found: Check the wiring, the power and `i2cdetect -y 1`")


def read(adc, ch):
    """One channel as text, or "over" if it is beyond the range."""
    try:
        return f"{adc.read_voltage(ch):5.3f}"
    except InputRangeError:
        return " over"


try:
    while True:
        line = []
        for addr, adc in boards.items():
            volts = " ".join(read(adc, ch) for ch in range(4))
            line.append(f"0x{addr:02X}: {volts}")
        print("  |  ".join(line))
        time.sleep(1)
except BusError as exc:
    raise SystemExit(exc)
except KeyboardInterrupt:
    pass
