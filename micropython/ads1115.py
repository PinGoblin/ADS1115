"""MicroPython module for the PinGoblin ADS1115 4-channel ADC breakout.

Runs on the ESP32, Raspberry Pi Pico and any other MicroPython board with `machine.I2C`.
It has no dependencies: copy this file to the board with Thonny or
`mpremote cp ads1115.py :`.

Each read starts a single-shot conversion, waits for it to finish and returns the result.
For faster sampling, use [`start()`][ads1115.ADS1115.start] with the RDY pin
(see `ready_pin_fast.py`).

Example:
    ```python
    from machine import I2C, Pin
    from ads1115 import ADS1115

    i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400_000)   # ESP32 defaults
    adc = ADS1115(i2c)                  # address 0x48, ±4.096 V, 128 samples/s
    print(adc.read_voltage(0))          # CH0 (header J2), volts
    ```
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
    """One ADS1115 breakout on an I²C bus.

    Args:
        i2c (machine.I2C): A `machine.I2C` (or `SoftI2C`) object. 100 kHz and 400 kHz both work.
        address: I²C address set by the address jumpers: `0x48` (default), `0x49`, `0x4A` or `0x4B`.
        fsr: Full-scale range (±V): 6.144, 4.096, 2.048, 1.024, 0.512 or 0.256.
            Use 4.096 on a 3.3 V board.
        rate: Samples per second: 8, 16, 32, 64, 128, 250, 475 or 860.

    Raises:
        ValueError: If `fsr` or `rate` is not one of the allowed values.

    Attributes:
        i2c: The I²C bus.
        address (int): The board's I²C address.
        fsr (float): Full-scale range (±V). Can be changed between reads.
        rate (int): Samples per second. Can be changed between reads.
    """

    def __init__(self, i2c, address: int = 0x48, fsr: float = 4.096, rate: int = 128):
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
    def read_raw(self, channel: int) -> int:
        """Read one single-ended channel as a raw count.

        Args:
            channel: Channel number, 0 to 3 (CH0 is header J2, CH3 is J5).

        Returns:
            Signed 16-bit result, −32768 to 32767. Full scale (32767) equals `fsr`.

        Raises:
            OSError: If the board does not answer on the I²C bus.
        """
        return self._convert(_MUX_SINGLE[channel])

    def read_voltage(self, channel: int, samples: int = 1) -> float:
        """Read one single-ended channel in volts.

        Args:
            channel: Channel number, 0 to 3.
            samples: Number of conversions to average.

        Returns:
            Mean voltage (V).

        Raises:
            OSError: If the board does not answer on the I²C bus.
        """
        total = 0
        for _ in range(samples):
            total += self.read_raw(channel)
        return total / samples * self.fsr / 32768

    def read_differential(self, pos: int, neg: int) -> float:
        """Read the voltage between two inputs.

        Both inputs must stay between GND and VDD, and both channels' RES jumpers must be open.

        Args:
            pos: Positive input channel.
            neg: Negative input channel. Valid pairs are (0, 1), (0, 3), (1, 3) and (2, 3).

        Returns:
            Voltage `pos − neg` (V); can be negative.

        Raises:
            KeyError: If the pair is not one the ADS1115 supports.
        """
        return self._convert(_MUX_DIFF[(pos, neg)]) * self.fsr / 32768

    def enable_ready_pin(self) -> None:
        """Make the RDY pin pulse low each time a conversion finishes.

        RDY is J1 pin 5 (the chip's ALERT/RDY pin), pulled up to VDD on the board. Wire it to
        a GPIO and trigger an interrupt on the falling edge. The Qwiic connectors do not
        carry RDY.
        """
        self._write(_REG_HI_THRESH, 0x8000)
        self._write(_REG_LO_THRESH, 0x0000)
        self._comp = _COMP_ASSERT_1

    def start(self, channel: int) -> None:
        """Start a conversion and return at once, without waiting for the result.

        Read the result with [`result_voltage()`][ads1115.ADS1115.result_voltage] after the
        RDY pin pulses (see [`enable_ready_pin()`][ads1115.ADS1115.enable_ready_pin]), or
        after `1/rate` seconds.

        Args:
            channel: Channel number, 0 to 3.
        """
        self._write(_REG_CONFIG, self._config(_MUX_SINGLE[channel]))

    def result_voltage(self) -> float:
        """Read the result of the last conversion.

        Returns:
            Voltage (V) from the conversion register, scaled by `fsr`.
        """
        raw = self._read(_REG_CONVERSION)
        raw = raw - 0x10000 if raw & 0x8000 else raw
        return raw * self.fsr / 32768
