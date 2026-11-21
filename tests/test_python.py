"""Tests for the Raspberry Pi module and examples, using a fake Adafruit library (no hardware)."""
import math
import os
import runpy
import sys
import tempfile
import time
import types

PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "python")
sys.path.insert(0, PY)
TMP = tempfile.mkdtemp()
import breakout_ads as b

# --- maths checks ---------------------------------------------------------
assert abs(b.resistance_from_voltage(1.65, 3.3) - 10000) < 1e-6          # equal divider
assert b.resistance_from_voltage(3.3, 3.3) == math.inf
assert abs(b.ntc_celsius(10000) - 25.0) < 1e-9
t = b.ntc_celsius(3588)   # typical 10k B3950 table: ~3.59k at 50 C
assert 49 < t < 51, t
t = b.ntc_celsius(32650)  # ~32.6k at 0 C
assert -1 < t < 1, t
assert b.percent_of_range(1.65, 0, 3.3) == 50.0
print("maths OK")

# --- fake Adafruit library + board, then run example 1 briefly --------------
VOLTS = [1.0, 1.65, 2.5, 3.0]
class FakeADS:
    def __init__(self, i2c, address=0x48):
        if address not in (0x48, 0x49): raise OSError("no device")
        self.address = address; self.gain = 1; self.data_rate = 128
class FakeIn:
    def __init__(self, ads, p, n=None): self.p = p
    @property
    def voltage(self): return VOLTS[self.p]
    @property
    def value(self): return int(VOLTS[self.p] / 4.096 * 32768)
pkg = types.ModuleType("adafruit_ads1x15"); pkg.ADS1115 = FakeADS; pkg.AnalogIn = FakeIn
sys.modules["adafruit_ads1x15"] = pkg
board = types.ModuleType("board"); board.I2C = lambda: object(); sys.modules["board"] = board

calls = {"n": 0}
real_sleep = time.sleep
def fake_sleep(s):
    calls["n"] += 1
    if calls["n"] >= 2: raise KeyboardInterrupt
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
# calibration: true 3.0 V on CH3 reading 3.0 -> factor 1
b.CAL_FILE = os.path.join(TMP, "cal.json")
sys.argv = ["06", "3", "3.003"]
import breakout_ads; breakout_ads.CAL_FILE = os.path.join(TMP, "cal.json")
g = runpy.run_path(os.path.join(PY, "06_calibrate.py"), run_name="__main__")
time.sleep = real_sleep
print("pi examples OK")
