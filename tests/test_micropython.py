"""Tests for the MicroPython driver against a simulated ADS1115 register map (runs on CPython)."""
import os
import sys
import time

time.sleep_us = lambda us: None
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "micropython"))
from ads1115 import ADS1115

class FakeChip:
    """Simulates ADS1115 registers; AIN voltages per channel."""
    def __init__(self, volts): self.v = volts; self.reg = {0:0, 1:0x8583, 2:0x8000, 3:0x7FFF}; self.writes=[]
    def writeto_mem(self, addr, reg, buf):
        val = (buf[0] << 8) | buf[1]; self.writes.append((reg, val))
        if reg == 1:
            mux = (val >> 12) & 7; pga = (val >> 9) & 7
            fsr = [6.144, 4.096, 2.048, 1.024, 0.512, 0.256][pga]
            if mux >= 4: v = self.v[mux - 4]
            else: v = {0:self.v[0]-self.v[1], 1:self.v[0]-self.v[3], 2:self.v[1]-self.v[3], 3:self.v[2]-self.v[3]}[mux]
            raw = max(-32768, min(32767, round(v / fsr * 32768)))
            self.reg[0] = raw & 0xFFFF; self.reg[1] = val | 0x8000
        else: self.reg[reg] = val
    def readfrom_mem_into(self, addr, reg, buf):
        buf[0] = self.reg[reg] >> 8; buf[1] = self.reg[reg] & 0xFF

chip = FakeChip([1.0, 1.65, 0.2, 3.0])
adc = ADS1115(chip)
for ch, v in enumerate(chip.v):
    got = adc.read_voltage(ch)
    assert abs(got - v) < 0.0002, (ch, got, v)
d = adc.read_differential(2, 3); assert abs(d - (0.2 - 3.0)) < 0.0002, d   # negative result
cfg = [w for w in chip.writes if w[0] == 1][0][1]
assert cfg == 0x8000 | 0x4000 | 0x0200 | 0x0100 | 0x0080 | 0x0003, hex(cfg)   # 0xC383 = AIN0, 4.096, single, 128 SPS
assert hex(cfg) == "0xc383"
adc.enable_ready_pin(); adc.start(1)
assert (2, 0x0000) in chip.writes and (3, 0x8000) in chip.writes
assert chip.writes[-1][1] & 3 == 0   # comparator queue enabled for ready pulses
assert abs(adc.result_voltage() - 1.65) < 0.0002
print("MicroPython driver OK, config word", hex(cfg))
