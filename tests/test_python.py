"""Tests for the Raspberry Pi package and examples, using a simulated ADS1115 on a fake smbus2 bus."""
import math
import os
import runpy
import sys
import tempfile
import threading
import time
import types

PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "python")
sys.path.insert(0, PY)
TMP = tempfile.mkdtemp()


# --- simulated chips on a fake smbus2 bus --------------------------------------
class FakeChip:
    """ADS1115 register map; AIN voltages per channel."""
    def __init__(self, volts):
        self.v = volts
        self.reg = {0: 0, 1: 0x8583, 2: 0x8000, 3: 0x7FFF}
        self.writes = []

    def write(self, reg, val):
        self.writes.append((reg, val))
        if reg == 1:
            mux = (val >> 12) & 7
            pga = (val >> 9) & 7
            fsr = [6.144, 4.096, 2.048, 1.024, 0.512, 0.256][pga]
            if mux >= 4:
                v = self.v[mux - 4]
            else:
                v = {0: self.v[0] - self.v[1], 1: self.v[0] - self.v[3],
                     2: self.v[1] - self.v[3], 3: self.v[2] - self.v[3]}[mux]
            raw = max(-32768, min(32767, round(v / fsr * 32768)))
            self.reg[0] = raw & 0xFFFF
            self.reg[1] = val | 0x8000
        else:
            self.reg[reg] = val


CHIPS = {0x48: FakeChip([1.0, 1.65, 0.2, 3.0]), 0x49: FakeChip([0.5, 0.5, 0.5, 0.5])}


class FakeSMBus:
    def __init__(self, bus=1):
        self.closed = False

    def _chip(self, addr):
        if addr not in CHIPS:
            raise OSError(121, "Remote I/O error")
        return CHIPS[addr]

    def write_i2c_block_data(self, addr, reg, data):
        self._chip(addr).write(reg, (data[0] << 8) | data[1])

    def read_i2c_block_data(self, addr, reg, n):
        val = self._chip(addr).reg[reg]
        return [val >> 8, val & 0xFF]

    def close(self):
        self.closed = True


fake = types.ModuleType("smbus2")
fake.SMBus = FakeSMBus
sys.modules["smbus2"] = fake

import pingoblin_ads1115 as p
from pingoblin_ads1115 import ads1115 as drv

drv.time = types.SimpleNamespace(sleep=lambda s: None)   # no real waits in the driver

# --- maths checks ---------------------------------------------------------
assert abs(p.resistance_from_voltage(1.65, 3.3) - 10000) < 1e-6          # equal divider
assert p.resistance_from_voltage(3.3, 3.3) == math.inf
assert abs(p.ntc_celsius(10000) - 25.0) < 1e-9
t = p.ntc_celsius(3588)   # typical 10k B3950 table: ~3.59k at 50 C
assert 49 < t < 51, t
t = p.ntc_celsius(32650)  # ~32.6k at 0 C
assert -1 < t < 1, t
assert p.percent_of_range(1.65, 0, 3.3) == 50.0
print("maths OK")

# --- driver -----------------------------------------------------------------
adc = p.ADS1115()
for ch, v in enumerate(CHIPS[0x48].v):
    got = adc.read_voltage(ch)
    assert abs(got - v) < 0.0002, (ch, got, v)
assert abs(adc.read_voltage(1, samples=4) - 1.65) < 0.0002
d = adc.read_differential(2, 3)
assert abs(d - (0.2 - 3.0)) < 0.0002, d          # negative result
cfg = [w for w in CHIPS[0x48].writes if w[0] == 1][0][1]
assert cfg == 0xC383, hex(cfg)                    # AIN0, ±4.096 V, single-shot, 128 SPS, comparator off
assert adc.read_raw(3) == round(3.0 / 4.096 * 32768)
adc.enable_ready_pin()
adc.start(1)
assert (2, 0x0000) in CHIPS[0x48].writes and (3, 0x8000) in CHIPS[0x48].writes
assert CHIPS[0x48].writes[-1][1] & 3 == 0         # comparator queue enabled for ready pulses
assert abs(adc.result_voltage() - 1.65) < 0.0002
adc.close()
assert adc._bus.closed
shared = FakeSMBus()
with p.ADS1115(shared, address=0x49, fsr=2.048, rate=860) as a2:
    assert abs(a2.read_voltage(0) - 0.5) < 0.0002
assert not shared.closed                          # a bus passed in is not closed
for bad in (dict(address=0x50), dict(fsr=5.0), dict(rate=100)):
    try:
        p.ADS1115(**bad)
        raise AssertionError(bad)
    except ValueError:
        pass
for call in (lambda: adc.read_raw(4), lambda: adc.read_differential(1, 2)):
    try:
        call()
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
try:
    p.ADS1115(address=0x4A).read_raw(0)
    raise AssertionError("expected OSError")
except OSError:
    pass
assert sorted(p.find_boards()) == [0x48, 0x49]

# thread safety: concurrent readers on one board get their own channel's result
errors = []
def reader(ch):
    a = shared_adc
    for _ in range(200):
        if abs(a.read_voltage(ch) - CHIPS[0x48].v[ch]) > 0.0002:
            errors.append(ch)
shared_adc = p.ADS1115()
threads = [threading.Thread(target=reader, args=(ch,)) for ch in range(4)]
for th in threads:
    th.start()
for th in threads:
    th.join()
assert not errors, errors
print("driver OK")

# --- run every example briefly ---------------------------------------------
calls = {"n": 0}
real_sleep = time.sleep
def fake_sleep(s):
    calls["n"] += 1
    if calls["n"] >= 2:
        raise KeyboardInterrupt
time.sleep = fake_sleep
os.chdir(TMP)
for script in ["01_read_all_channels.py", "02_thermistor_ntc.py", "03_light_and_pot.py", "04_multiple_boards.py"]:
    calls["n"] = 0
    print("---", script)
    runpy.run_path(os.path.join(PY, script), run_name="__main__")
calls["n"] = 0
sys.argv = ["05", "1", os.path.join(TMP, "log.csv")]
runpy.run_path(os.path.join(PY, "05_csv_logger.py"), run_name="__main__")
print(open(os.path.join(TMP, "log.csv")).read())
sys.argv = ["06", "3", "3.003"]
runpy.run_path(os.path.join(PY, "06_calibrate.py"), run_name="__main__")
cal = p.load_calibration()                       # written to calibration.json in the working directory
assert abs(cal["3"] - 1.001) < 0.0005, cal
time.sleep = real_sleep
print("pi examples OK")
