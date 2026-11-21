"""
Minimal MicroPython driver for the 4-channel ADS1115 breakout (ESP32, Pico, etc.).

Copy this file to the board (e.g. with Thonny or `mpremote cp ads1115.py :`).

    from machine import I2C, Pin
    from ads1115 import ADS1115
    i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400_000)   # ESP32 defaults
    adc = ADS1115(i2c)                  # address 0x48, +/-4.096 V
    print(adc.read_voltage(0))
"""
import time

_REG_CONVERSION = 0x00
_REG_CONFIG = 0x01
_REG_LO_THRESH = 0x02
_REG_HI_THRESH = 0x03

# Full-scale range (V) -> PGA bits
_PGA = {6.144: 0x0000, 4.096: 0x0200, 2.048: 0x0400, 1.024: 0x0600, 0.512: 0x0800, 0.256: 0x0A00}
# Samples per second -> DR bits
_DR = {8: 0x0000, 16: 0x0020, 32: 0x0040, 64: 0x0060, 128: 0x0080, 250: 0x00A0, 475: 0x00C0, 860: 0x00E0}
# Single-ended MUX settings AIN0..AIN3 vs GND
_MUX_SINGLE = (0x4000, 0x5000, 0x6000, 0x7000)
# Differential: (0,1) (0,3) (1,3) (2,3)
_MUX_DIFF = {(0, 1): 0x0000, (0, 3): 0x1000, (1, 3): 0x2000, (2, 3): 0x3000}

_OS_START = 0x8000
_MODE_SINGLE = 0x0100
_COMP_DISABLE = 0x0003
_COMP_ASSERT_1 = 0x0000   # ALERT/RDY asserts after every conversion (ready mode)


class ADS1115:
    def __init__(self, i2c, address=0x48, fsr=4.096, rate=128):
        if fsr not in _PGA:
            raise ValueError("fsr must be one of %s" % sorted(_PGA))
        if rate not in _DR:
            raise ValueError("rate must be one of %s" % sorted(_DR))
        self.i2c = i2c
        self.address = address
        self.fsr = fsr
        self.rate = rate
        self._comp = _COMP_DISABLE
        self._buf = bytearray(2)

    # -- low level ---------------------------------------------------------
    def _write(self, reg, value):
        self._buf[0] = (value >> 8) & 0xFF
        self._buf[1] = value & 0xFF
        self.i2c.writeto_mem(self.address, reg, self._buf)

    def _read(self, reg):
        self.i2c.readfrom_mem_into(self.address, reg, self._buf)
        return (self._buf[0] << 8) | self._buf[1]

    def _config(self, mux):
        return _OS_START | mux | _PGA[self.fsr] | _MODE_SINGLE | _DR[self.rate] | self._comp

    def _convert(self, mux):
        self._write(_REG_CONFIG, self._config(mux))
        # one conversion takes 1/rate seconds; poll the OS bit until done
        time.sleep_us(int(1_000_000 / self.rate) + 100)
        for _ in range(100):
            if self._read(_REG_CONFIG) & _OS_START:
                break
            time.sleep_us(100)
        raw = self._read(_REG_CONVERSION)
        return raw - 0x10000 if raw & 0x8000 else raw

    # -- public API --------------------------------------------------------
    def read_raw(self, channel):
        """Signed 16-bit result for single-ended channel 0-3."""
        return self._convert(_MUX_SINGLE[channel])

    def read_voltage(self, channel, samples=1):
        total = 0
        for _ in range(samples):
            total += self.read_raw(channel)
        return total / samples * self.fsr / 32768

    def read_differential(self, pos, neg):
        """Voltage between two inputs, e.g. (0, 1) or (2, 3)."""
        return self._convert(_MUX_DIFF[(pos, neg)]) * self.fsr / 32768

    def enable_ready_pin(self):
        """Make the RDY pin (J1 pin 5, the chip's ALERT/RDY) pulse low when each conversion finishes."""
        self._write(_REG_HI_THRESH, 0x8000)
        self._write(_REG_LO_THRESH, 0x0000)
        self._comp = _COMP_ASSERT_1

    def start(self, channel):
        """Start a conversion and return immediately (use with the ready pin)."""
        self._write(_REG_CONFIG, self._config(_MUX_SINGLE[channel]))

    def result_voltage(self):
        raw = self._read(_REG_CONVERSION)
        raw = raw - 0x10000 if raw & 0x8000 else raw
        return raw * self.fsr / 32768
