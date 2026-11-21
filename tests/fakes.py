"""Hardware fakes shared by the tests.

- `ADS1115Chip`: register-level model of one ADS1115 (config, conversion and threshold
  registers, OS busy bit, ALERT/RDY behaviour), written from the datasheet rather than
  from the code under test.
- `FakeI2C` and `make_machine()`: a MicroPython `machine` module with I2C and Pin.
- `MicroPythonTime`: a MicroPython `time` module with `sleep_us` and the `ticks_*` functions.
- `FakeAdafruit`: the Adafruit ADS1x15 library (2.x or 3.x layout) plus Blinka's `board`.
- `run_script()`: runs an example script as `__main__` and captures its output.
"""
import contextlib
import importlib.util
import io
import os
import sys
import types
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PY_DIR = os.path.join(ROOT, "python")
MP_DIR = os.path.join(ROOT, "micropython")
DOCS_DIR = os.path.join(ROOT, "docs")

# Datasheet (SBAS444) register fields
REG_CONVERSION, REG_CONFIG, REG_LO_THRESH, REG_HI_THRESH = 0, 1, 2, 3
FSR_BY_PGA = (6.144, 4.096, 2.048, 1.024, 0.512, 0.256, 0.256, 0.256)
DIFF_BY_MUX = {0: (0, 1), 1: (0, 3), 2: (1, 3), 3: (2, 3)}


class StopScript(Exception):
    """Raised by a fake sleep to end an example's endless loop."""


# ---------------------------------------------------------------------------
# ADS1115 register model
# ---------------------------------------------------------------------------
class ADS1115Chip:
    """One ADS1115 with fixed input voltages on AIN0–AIN3.

    Args:
        volts: Voltage on each input.
        busy_polls: Config reads that return OS=0 (busy) after each conversion starts.
        never_ready: If true, OS never returns to 1.
    """

    def __init__(self, volts=(0.0, 0.0, 0.0, 0.0), busy_polls=0, never_ready=False):
        self.volts = list(volts)
        self.busy_polls = busy_polls
        self.never_ready = never_ready
        # Power-on reset values
        self.reg = {REG_CONVERSION: 0x0000, REG_CONFIG: 0x8583,
                    REG_LO_THRESH: 0x8000, REG_HI_THRESH: 0x7FFF}
        self.writes = []         # (register, value) for every write
        self.config_reads = 0
        self.conversions = 0
        self.on_ready = None     # called when ALERT/RDY would pulse
        self._busy = 0

    @staticmethod
    def to_raw(volts, fsr):
        """Ideal 16-bit result, clipped to the output code range."""
        return max(-32768, min(32767, round(volts / fsr * 32768)))

    def input_voltage(self, mux):
        if mux >= 4:
            return self.volts[mux - 4]
        pos, neg = DIFF_BY_MUX[mux]
        return self.volts[pos] - self.volts[neg]

    def rdy_enabled(self):
        """Conversion-ready mode: comparator on, Hi_thresh MSB 1 and Lo_thresh MSB 0."""
        return ((self.reg[REG_CONFIG] & 0x3) != 0x3
                and self.reg[REG_HI_THRESH] & 0x8000
                and not self.reg[REG_LO_THRESH] & 0x8000)

    def config_writes(self):
        return [v for r, v in self.writes if r == REG_CONFIG]

    def write(self, reg, data):
        if len(data) != 2:
            raise AssertionError("ADS1115 registers are 16 bits; got %d bytes" % len(data))
        if reg not in self.reg:
            raise AssertionError("no register %d" % reg)
        value = (data[0] << 8) | data[1]
        self.writes.append((reg, value))
        if reg == REG_CONFIG:
            self.reg[REG_CONFIG] = value & 0x7FFF      # OS reads 0 while converting
            if value & 0x8000:
                self._convert(value)
        elif reg != REG_CONVERSION:                     # conversion register is read-only
            self.reg[reg] = value

    def _convert(self, config):
        mux = (config >> 12) & 0x7
        fsr = FSR_BY_PGA[(config >> 9) & 0x7]
        self.reg[REG_CONVERSION] = self.to_raw(self.input_voltage(mux), fsr) & 0xFFFF
        self.conversions += 1
        self._busy = self.busy_polls
        if self.rdy_enabled() and self.on_ready:
            self.on_ready()

    def read(self, reg):
        value = self.reg[reg]
        if reg == REG_CONFIG:
            self.config_reads += 1
            if self.never_ready:
                return value
            if self._busy > 0:
                self._busy -= 1
                return value
            return value | 0x8000
        return value


# ---------------------------------------------------------------------------
# MicroPython machine and time modules
# ---------------------------------------------------------------------------
class FakeI2C:
    """MicroPython I2C bus with ADS1115Chip objects at their addresses."""

    def __init__(self, chips):
        self.chips = dict(chips)

    def scan(self):
        return sorted(self.chips)

    def _chip(self, addr):
        try:
            return self.chips[addr]
        except KeyError:
            raise OSError(19, "ENODEV") from None   # what MicroPython raises on a NACK

    def writeto_mem(self, addr, reg, buf):
        self._chip(addr).write(reg, bytes(buf))

    def readfrom_mem_into(self, addr, reg, buf):
        value = self._chip(addr).read(reg)
        buf[0] = value >> 8
        buf[1] = value & 0xFF


def make_machine(bus):
    """Build a fake `machine` module whose I2C constructor returns `bus`."""
    machine = types.ModuleType("machine")
    machine.pins = {}
    machine.i2c_calls = []

    class Pin:
        IN, OUT, PULL_UP, PULL_DOWN, IRQ_FALLING, IRQ_RISING = 1, 2, 3, 4, 5, 6

        def __init__(self, pin_id, mode=None, pull=None):
            self.id, self.mode, self.pull = pin_id, mode, pull
            self.trigger = self.handler = None
            machine.pins[pin_id] = self

        def irq(self, trigger=None, handler=None):
            self.trigger, self.handler = trigger, handler

        def fire(self):
            if self.handler:
                self.handler(self)

    def I2C(bus_id, scl=None, sda=None, freq=400_000):
        machine.i2c_calls.append({"id": bus_id, "scl": scl.id, "sda": sda.id, "freq": freq})
        return bus

    machine.Pin = Pin
    machine.I2C = I2C
    machine.SoftI2C = I2C
    return machine


class MicroPythonTime(types.ModuleType):
    """MicroPython-style `time` module with a fake clock.

    Args:
        sleep_limit: Raise `StopScript` on this many calls to `sleep()`.
    """

    def __init__(self, sleep_limit=None):
        super().__init__("time")
        self.sleep_limit = sleep_limit
        self.sleeps = []
        self.slept_us = []
        self._ms = 0

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        if self.sleep_limit is not None and len(self.sleeps) >= self.sleep_limit:
            raise StopScript

    def sleep_us(self, us):
        self.slept_us.append(us)

    def sleep_ms(self, ms):
        self.slept_us.append(ms * 1000)

    def ticks_ms(self):
        self._ms += 1
        return self._ms

    @staticmethod
    def ticks_add(ticks, delta):
        return ticks + delta

    @staticmethod
    def ticks_diff(a, b):
        return a - b


def load_ads1115(time_module):
    """Import a fresh copy of micropython/ads1115.py that uses `time_module`."""
    spec = importlib.util.spec_from_file_location("ads1115", os.path.join(MP_DIR, "ads1115.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.time = time_module
    return module


# ---------------------------------------------------------------------------
# Adafruit ADS1x15 library and Blinka
# ---------------------------------------------------------------------------
class FakeAdafruit:
    """Fake `adafruit_ads1x15` plus `board`.

    Args:
        boards: I²C address to the four input voltages of the board at that address.
            A voltage can be a list, which is read in turn (the last value repeats).
        layout: 3 for library 3.x (classes in the package), 2 for 2.x (submodules).
    """

    GAIN_FSR = {2 / 3: 6.144, 1: 4.096, 2: 2.048, 4: 1.024, 8: 0.512, 16: 0.256}

    def __init__(self, boards, layout=3):
        self.boards = boards
        self.layout = layout
        self.devices = []
        self.reads = 0
        self.i2c = object()
        fake = self

        class ADS1115:
            def __init__(self, i2c, gain=1, data_rate=None, address=0x48):
                if address not in fake.boards:
                    raise ValueError("No I2C device at address: 0x%x" % address)
                self.i2c, self.address = i2c, address
                self.gain, self.data_rate = gain, data_rate or 128
                fake.devices.append(self)

        class AnalogIn:
            def __init__(self, ads, positive_pin, negative_pin=None):
                self.ads, self.pos, self.neg = ads, positive_pin, negative_pin

            def _volts(self, ch):
                v = fake.boards[self.ads.address][ch]
                if isinstance(v, list):
                    return v.pop(0) if len(v) > 1 else v[0]
                return v

            @property
            def voltage(self):
                fake.reads += 1
                v = self._volts(self.pos)
                if self.neg is not None:
                    v -= self._volts(self.neg)
                return v

            @property
            def value(self):
                return ADS1115Chip.to_raw(self.voltage, fake.GAIN_FSR[self.ads.gain])

        self.ADS1115, self.AnalogIn = ADS1115, AnalogIn

    def modules(self):
        """Entries to patch into `sys.modules`."""
        pkg = types.ModuleType("adafruit_ads1x15")
        pkg.__path__ = []
        mods = {"adafruit_ads1x15": pkg}
        if self.layout == 3:
            pkg.ADS1115, pkg.AnalogIn = self.ADS1115, self.AnalogIn
        else:
            ads_mod = types.ModuleType("adafruit_ads1x15.ads1115")
            ads_mod.ADS1115 = self.ADS1115
            ain_mod = types.ModuleType("adafruit_ads1x15.analog_in")
            ain_mod.AnalogIn = self.AnalogIn
            mods.update({"adafruit_ads1x15.ads1115": ads_mod, "adafruit_ads1x15.analog_in": ain_mod})
        board = types.ModuleType("board")
        board.I2C = lambda: self.i2c
        mods["board"] = board
        return mods


# ---------------------------------------------------------------------------
# Running example scripts
# ---------------------------------------------------------------------------
def run_script(path, argv=(), modules=None, cwd=None, edits=None):
    """Run a script as `__main__`.

    `edits` maps text in the script to its replacement, to change a setting at the top of an
    example the way a user would.

    Returns:
        `(globals, stdout, exception)`, where exception is the `SystemExit` or
        `StopScript` that ended the script, or `None` if it finished normally.
    """
    with open(path, encoding="utf-8") as f:
        source = f.read()
    for old, new in (edits or {}).items():
        if source.count(old) != 1:
            raise AssertionError("%r not found once in %s" % (old, path))
        source = source.replace(old, new)
    code = compile(source, path, "exec")
    namespace = {"__name__": "__main__", "__file__": path}
    out = io.StringIO()
    exc = None
    with contextlib.ExitStack() as stack:
        if modules:
            stack.enter_context(mock.patch.dict(sys.modules, modules))
        stack.enter_context(mock.patch.object(sys, "argv", [path, *argv]))
        if cwd:
            stack.enter_context(contextlib.chdir(cwd))
        stack.enter_context(contextlib.redirect_stdout(out))
        try:
            exec(code, namespace)
        except (SystemExit, StopScript) as e:
            exc = e
    return namespace, out.getvalue(), exc
