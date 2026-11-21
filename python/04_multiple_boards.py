#!/usr/bin/env python3
"""
Example 4 - Several boards on one I2C bus (up to 16 channels).

Give every board a different address with the solder jumpers:
  board A: JP1 closed (default)                -> 0x48
  board B: cut JP1, close JP2                  -> 0x49
  board C: cut JP1, close JP3                  -> 0x4A
  board D: cut JP1, close JP4                  -> 0x4B
Daisy-chain them with Qwiic cables (J6 -> J7 of the next board).

Tip: `i2cdetect -y 1` lists the addresses the Pi can see.
"""
import time

from breakout_ads import open_adc, channel

CANDIDATES = [0x48, 0x49, 0x4A, 0x4B]

boards = {}
for addr in CANDIDATES:
    try:
        ads = open_adc(address=addr, gain=1)
        chans = [channel(ads, ch) for ch in range(4)]
        chans[0].value                      # test read - raises if absent
        boards[addr] = chans
        print(f"Found board at 0x{addr:02X}")
    except (OSError, ValueError, RuntimeError):
        pass

if not boards:
    raise SystemExit("No boards found - check wiring, power and `i2cdetect -y 1`.")

try:
    while True:
        line = []
        for addr, chans in boards.items():
            volts = " ".join(f"{c.voltage:5.3f}" for c in chans)
            line.append(f"0x{addr:02X}: {volts}")
        print("  |  ".join(line))
        time.sleep(1)
except KeyboardInterrupt:
    pass
