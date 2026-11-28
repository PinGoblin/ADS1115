"""Hardware fakes shared by the tests.

- `ADS1115Chip`: register-level model of one ADS1115 (config, conversion and threshold
  registers, OS busy bit, sign and clipping, ALERT/RDY), written from the datasheet rather
  than from the code under test.
- `make_smbus2()`: an `smbus2` module whose `SMBus` talks to `ADS1115Chip` objects (Pi side).
- `FakeI2C`, `make_machine()`, `MicroPythonTime`: MicroPython `machine` and `time` modules.
- `load_pi_driver()`, `load_mp_driver()`: fresh copies of the code under test.
- `run_script()`: runs an example script as `__main__` and captures its output.
"""
import contextlib
import importlib
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

# Datasheet (SBAS444) register map
REG_CONVERSION, REG_CONFIG, REG_LO_THRESH, REG_HI_THRESH = 0, 1, 2, 3
FSR_BY_PGA = (6.144, 4.096, 2.048, 1.024, 0.512, 0.256, 0.256, 0.256)
DIFF_BY_MUX = {0: (0, 1), 1: (0, 3), 2: (1, 3), 3: (2, 3)}

# Config-register fields, written out independently of the drivers
OS = 0x8000
MUX_SINGLE = {0: 0x4000, 1: 0x5000, 2: 0x6000, 3: 0x7000}
MUX_DIFF = {(0, 1): 0x0000, (0, 3): 0x1000, (1, 3): 0x2000, (2, 3): 0x3000}
PGA = {6.144: 0x0000, 4.096: 0x0200, 2.048: 0x0400, 1.024: 0x0600, 0.512: 0x0800, 0.256: 0x0A00}
DR = {8: 0x0000, 16: 0x0020, 32: 0x0040, 64: 0x0060, 128: 0x0080, 250: 0x00A0, 475: 0x00C0, 860: 0x00E0}
MODE_SINGLE = 0x0100
MUX_MASK, PGA_MASK, DR_MASK, QUE_MASK = 0x7000, 0x0E00, 0x00E0, 0x0003


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
        return bool((self.reg[REG_CONFIG] & 0x3) != 0x3
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
            if value & OS:
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
            return value | OS
        return value


# ---------------------------------------------------------------------------
# Raspberry Pi side: smbus2
# ---------------------------------------------------------------------------
def make_smbus2(chips):
    """Build a fake `smbus2` module whose buses reach `chips` (address -> ADS1115Chip)."""
    module = types.ModuleType("smbus2")
    module.opened = []

    class SMBus:
        def __init__(self, bus=None):
            self.bus = bus
            self.closed = False
            module.opened.append(self)

        def _chip(self, addr):
            if self.closed:
                raise OSError(9, "Bad file descriptor")
            try:
                return chips[addr]
            except KeyError:
                raise OSError(121, "Remote I/O error") from None   # what Linux reports on a NACK

        def write_i2c_block_data(self, addr, reg, data):
            self._chip(addr).write(reg, bytes(data))

        def read_i2c_block_data(self, addr, reg, length):
            if length != 2:
                raise AssertionError("ADS1115 registers are 2 bytes")
            value = self._chip(addr).read(reg)
            return [value >> 8, value & 0xFF]

        def close(self):
            self.closed = True

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.close()

    module.SMBus = SMBus
    return module


class FakeSleep:
    """Records the driver's waits instead of sleeping."""

    def __init__(self):
        self.calls = []

    def sleep(self, seconds):
        self.calls.append(seconds)


def load_pi_driver():
    """Import `pingoblin_ads1115` from python/ (once) and return `(package, driver module)`."""
    if PY_DIR not in sys.path:
        sys.path.insert(0, PY_DIR)
    package = importlib.import_module("pingoblin_ads1115")
    return package, importlib.import_module("pingoblin_ads1115.ads1115")


# ---------------------------------------------------------------------------
# MicroPython side: machine and time
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


def load_mp_driver(time_module):
    """Import a fresh copy of micropython/ads1115.py that uses `time_module`."""
    spec = importlib.util.spec_from_file_location("ads1115", os.path.join(MP_DIR, "ads1115.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.time = time_module
    return module


# ---------------------------------------------------------------------------
# Running example scripts
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def working_directory(path):
    """`contextlib.chdir` for Python versions before 3.11."""
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


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
            stack.enter_context(working_directory(cwd))
        stack.enter_context(contextlib.redirect_stdout(out))
        try:
            exec(code, namespace)
        except (SystemExit, StopScript) as e:
            exc = e
    return namespace, out.getvalue(), exc
