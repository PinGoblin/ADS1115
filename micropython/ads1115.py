"""MicroPython module for the PinGoblin ADS1115 4-channel ADC board.

Runs on the ESP32, Raspberry Pi Pico and any other MicroPython board with `machine.I2C`.
It has no dependencies: Copy this file to the board with Thonny or
`mpremote cp ads1115.py :`.

Each read starts a single-shot conversion, waits for it to finish and returns the result.
For faster sampling, use [`start()`][ads1115.ADS1115.start] with the RDY pin
(see `ready_pin_fast.py`). [`MockI2C`][ads1115.MockI2C] simulates a board, so code also
runs without hardware.

Example:
    ```python
    from machine import I2C, Pin
    from ads1115 import ADS1115

    i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=100_000)   # ESP32 defaults
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
_FULL_SCALE = (32767, -32768)

ADDRESSES = (0x48, 0x49, 0x4A, 0x4B)
"""Valid I²C addresses: 0x48 (JP1, default), 0x49 (JP2), 0x4A (JP3) and 0x4B (JP4)."""


class BusError(OSError):
    """The board did not answer on the I²C bus. The message names the address and says what to check."""


class InputRangeError(ValueError):
    """A reading reached the full-scale range (±`fsr`), so its value is not valid.

    The input is beyond the range set with `fsr`. The message says which range to use instead.
    """


def _range_message(what, fsr):
    larger = [f for f in sorted(_PGA) if f > fsr]
    if larger:
        fix = "Use a larger range, for example ADS1115(i2c, fsr=%g)" % larger[0]
        if fsr == 4.096:
            fix += " on a board powered from 5 V"
    else:
        fix = "Keep every input between 0 V and VDD"
    return "%s is at the ±%g V full-scale limit, so the reading is not valid: %s" % (what, fsr, fix)


class ADS1115:
    """One PinGoblin ADS1115 board on an I²C bus.

    Args:
        i2c (machine.I2C): A `machine.I2C` (or `SoftI2C`) object, or a
            [`MockI2C`][ads1115.MockI2C]. Use 100 kHz with only the board's 10 kΩ pull-ups;
            400 kHz needs 2.2–4.7 kΩ pull-ups to 3.3 V at the host.
        address: I²C address set by the address jumpers: `0x48` (default), `0x49`, `0x4A` or `0x4B`.
        fsr: Full-scale range (±V): 6.144, 4.096, 2.048, 1.024, 0.512 or 0.256.
            Use 4.096 on a 3.3 V board and 6.144 on a 5 V board.
        rate: Samples per second: 8, 16, 32, 64, 128, 250, 475 or 860.

    Raises:
        ValueError: If `address`, `fsr` or `rate` is not one of the allowed values.

    Attributes:
        i2c: The I²C bus.
        address (int): The board's I²C address.
        fsr (float): Full-scale range (±V). Can be changed between reads.
        rate (int): Samples per second. Can be changed between reads.
    """

    def __init__(self, i2c, address: int = 0x48, fsr: float = 4.096, rate: int = 128):
        if address not in ADDRESSES:
            raise ValueError("address must be 0x48, 0x49, 0x4A or 0x4B (set by the address jumpers)")
        if fsr not in _PGA:
            raise ValueError("fsr must be one of %s" % sorted(_PGA))
        if rate not in _DR:
            raise ValueError("rate must be one of %s" % sorted(_DR))
        self.i2c = i2c
        self.address = address
        self.fsr = fsr
        self.rate = rate
        self._comp = _COMP_DISABLE
        self._started = 0
        self._buf = bytearray(2)

    # -- low level ---------------------------------------------------------
    def _bus_error(self, exc):
        return BusError("No answer from the board at 0x%02X (%s): Check the J1 wiring, the power "
                        "and the address jumpers" % (self.address, exc))

    def _write(self, reg, value):
        self._buf[0] = (value >> 8) & 0xFF
        self._buf[1] = value & 0xFF
        try:
            self.i2c.writeto_mem(self.address, reg, self._buf)
        except OSError as exc:
            raise self._bus_error(exc)

    def _read(self, reg):
        try:
            self.i2c.readfrom_mem_into(self.address, reg, self._buf)
        except OSError as exc:
            raise self._bus_error(exc)
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

    def _average(self, mux, samples, what):
        total = 0
        clipped = False
        for _ in range(samples):
            raw = self._convert(mux)
            clipped = clipped or raw in _FULL_SCALE
            total += raw
        if clipped:
            raise InputRangeError(_range_message(what, self.fsr))
        return total / samples * self.fsr / 32768

    # -- public API --------------------------------------------------------
    def read_raw(self, channel: int) -> int:
        """Read one single-ended channel as a raw count.

        Args:
            channel: Channel number, 0 to 3 (CH0 is header J2, CH3 is J5).

        Returns:
            Signed 16-bit result, −32768 to 32767. 32767 means the input is at or above `fsr`;
            [`read_voltage()`][ads1115.ADS1115.read_voltage] raises `InputRangeError` instead.

        Raises:
            ValueError: If `channel` is not 0 to 3.
            BusError: If the board does not answer on the I²C bus.

        Example:
            ```python
            raw = adc.read_raw(0)            # 13200 at 1.65 V with fsr=4.096
            ```
        """
        if channel not in (0, 1, 2, 3):
            raise ValueError("channel must be 0-3 (CH0 is J2, CH3 is J5)")
        return self._convert(_MUX_SINGLE[channel])

    def read_voltage(self, channel: int, samples: int = 1) -> float:
        """Read one single-ended channel in volts.

        Args:
            channel: Channel number, 0 to 3.
            samples: Number of conversions to average.

        Returns:
            Mean voltage (V).

        Raises:
            ValueError: If `channel` is not 0 to 3.
            InputRangeError: If any conversion reached the full-scale range.
            BusError: If the board does not answer on the I²C bus.

        Example:
            ```python
            volts = adc.read_voltage(0, samples=16)
            ```
        """
        if channel not in (0, 1, 2, 3):
            raise ValueError("channel must be 0-3 (CH0 is J2, CH3 is J5)")
        return self._average(_MUX_SINGLE[channel], samples, "CH%d" % channel)

    def read_differential(self, pos: int, neg: int, samples: int = 1) -> float:
        """Read the voltage between two inputs.

        Both inputs must stay between GND and VDD, and both channels' RES jumpers must be open.

        Args:
            pos: Positive input channel.
            neg: Negative input channel. Valid pairs are (0, 1), (0, 3), (1, 3) and (2, 3).
            samples: Number of conversions to average.

        Returns:
            Mean voltage `pos − neg` (V). It can be negative.

        Raises:
            ValueError: If the pair is not one the ADS1115 supports.
            InputRangeError: If any conversion reached the full-scale range.
            BusError: If the board does not answer on the I²C bus.

        Example:
            ```python
            shunt_volts = adc.read_differential(0, 1)
            ```
        """
        if (pos, neg) not in _MUX_DIFF:
            raise ValueError("differential pair must be (0, 1), (0, 3), (1, 3) or (2, 3)")
        return self._average(_MUX_DIFF[(pos, neg)], samples, "CH%d−CH%d" % (pos, neg))

    def enable_ready_pin(self) -> None:
        """Make the RDY pin pulse low each time a conversion finishes.

        RDY is J1 pin 5 (the chip's ALERT/RDY pin), pulled up to VDD on the board. Wire it to
        a GPIO and trigger an interrupt on the falling edge. Each board needs its own GPIO.

        Raises:
            BusError: If the board does not answer on the I²C bus.

        Example:
            ```python
            adc.enable_ready_pin()
            adc.start(0)                     # RDY falls when the result is ready
            ```
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

        Raises:
            ValueError: If `channel` is not 0 to 3.
            BusError: If the board does not answer on the I²C bus.

        Example:
            ```python
            adc.start(2)
            ```
        """
        if channel not in (0, 1, 2, 3):
            raise ValueError("channel must be 0-3 (CH0 is J2, CH3 is J5)")
        self._write(_REG_CONFIG, self._config(_MUX_SINGLE[channel]))
        self._started = channel

    def result_voltage(self) -> float:
        """Read the result of the last conversion started with `start()`.

        Returns:
            Voltage (V) from the conversion register, scaled by `fsr`.

        Raises:
            InputRangeError: If the result reached the full-scale range.
            BusError: If the board does not answer on the I²C bus.

        Example:
            ```python
            volts = adc.result_voltage()
            ```
        """
        raw = self._read(_REG_CONVERSION)
        raw = raw - 0x10000 if raw & 0x8000 else raw
        if raw in _FULL_SCALE:
            raise InputRangeError(_range_message("CH%d" % self._started, self.fsr))
        return raw * self.fsr / 32768


_SIM_FSR = (6.144, 4.096, 2.048, 1.024, 0.512, 0.256, 0.256, 0.256)
_SIM_DIFF = {0: (0, 1), 1: (0, 3), 2: (1, 3), 3: (2, 3)}


class MockI2C:
    """A simulated I²C bus with one or more boards on it, for running code without hardware.

    Pass it to [`ADS1115`][ads1115.ADS1115] in place of `machine.I2C`. Each simulated board
    answers like a real one: Conversions use the range and channel you set, readings beyond
    the range reach full scale, and an address with no board raises `OSError`.

    Example:
        ```python
        from ads1115 import ADS1115, MockI2C

        i2c = MockI2C()
        i2c.volts[0x48][2] = 0.75            # CH2 of the board at 0x48 now reads 0.75 V
        print(ADS1115(i2c).read_voltage(2))
        ```

    Args:
        volts: Input voltages CH0–CH3 (V), the same on every simulated board.
        addresses: I²C addresses of the simulated boards.

    Attributes:
        volts (dict): Input voltages CH0–CH3 of each board, by address. Change them to
            simulate a sensor.
    """

    def __init__(self, volts: tuple = (1.65, 1.65, 2.5, 3.0), addresses: tuple = (0x48,)):
        self.volts = {}
        self._regs = {}
        for addr in addresses:
            self.volts[addr] = list(volts)
            self._regs[addr] = {0: 0x0000, 1: 0x8583, 2: 0x8000, 3: 0x7FFF}

    def _board(self, addr):
        if addr not in self._regs:
            raise OSError(19, "ENODEV")
        return self._regs[addr]

    def scan(self) -> list:
        """List the addresses of the simulated boards.

        Returns:
            Sorted list of addresses, like `machine.I2C.scan()`.
        """
        return sorted(self._regs)

    def writeto_mem(self, addr: int, memaddr: int, buf: bytes) -> None:
        """Write a 16-bit register of the simulated board at `addr`.

        Args:
            addr: I²C address.
            memaddr: Register number, 0 to 3.
            buf: Two bytes, most significant first.

        Raises:
            OSError: If no simulated board has that address.
        """
        regs = self._board(addr)
        value = (buf[0] << 8) | buf[1]
        if memaddr == 1 and value & 0x8000:
            mux, fsr = (value >> 12) & 7, _SIM_FSR[(value >> 9) & 7]
            volts = self.volts[addr]
            v = volts[mux - 4] if mux >= 4 else volts[_SIM_DIFF[mux][0]] - volts[_SIM_DIFF[mux][1]]
            regs[0] = max(-32768, min(32767, round(v / fsr * 32768))) & 0xFFFF
        if memaddr != 0:
            regs[memaddr] = value

    def readfrom_mem_into(self, addr: int, memaddr: int, buf: bytearray) -> None:
        """Read a 16-bit register of the simulated board at `addr`. Conversions finish at once.

        Args:
            addr: I²C address.
            memaddr: Register number, 0 to 3.
            buf: Two-byte buffer to fill, most significant byte first.

        Raises:
            OSError: If no simulated board has that address.
        """
        value = self._board(addr)[memaddr]
        buf[0] = value >> 8
        buf[1] = value & 0xFF
