"""ADS1115 driver for the Raspberry Pi and other Linux boards, built on `smbus2`.

Talks to the chip directly over I²C, with the same methods as the MicroPython
[`ads1115`][ads1115] module. It is thread-safe: one conversion runs at a time, so several
threads (for example a motor library's fault monitor and your own code) can share one board.
"""
from __future__ import annotations

import threading
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

ADDRESSES = (0x48, 0x49, 0x4A, 0x4B)
"""Valid I²C addresses: 0x48 (JP1, default), 0x49 (JP2), 0x4A (JP3) and 0x4B (JP4)."""


class ADS1115:
    """One ADS1115 board on an I²C bus.

    Example:
        ```python
        from pingoblin_ads1115 import ADS1115

        with ADS1115(address=0x48) as adc:   # I²C bus 1, ±4.096 V, 128 samples/s
            print(adc.read_voltage(0))       # CH0 (header J2), volts
        ```

    Args:
        bus: I²C bus number (1 on a Raspberry Pi), or an open bus object with
            `write_i2c_block_data()` and `read_i2c_block_data()`, such as `smbus2.SMBus`.
        address: I²C address set by the address jumpers: `0x48` (default), `0x49`, `0x4A`
            or `0x4B`.
        fsr: Full-scale range (±V): 6.144, 4.096, 2.048, 1.024, 0.512 or 0.256.
            Use 4.096 on a 3.3 V board.
        rate: Samples per second: 8, 16, 32, 64, 128, 250, 475 or 860.
            Slower rates give lower noise.

    Raises:
        ValueError: If `address`, `fsr` or `rate` is not one of the allowed values.
        OSError: If the I²C bus cannot be opened.

    Attributes:
        address (int): The board's I²C address.
        fsr (float): Full-scale range (±V). Can be changed between reads.
        rate (int): Samples per second. Can be changed between reads.
    """

    def __init__(self, bus: int | object = 1, address: int = 0x48, fsr: float = 4.096, rate: int = 128):
        if address not in ADDRESSES:
            raise ValueError("address must be one of 0x48, 0x49, 0x4A or 0x4B")
        if fsr not in _PGA:
            raise ValueError(f"fsr must be one of {sorted(_PGA)}")
        if rate not in _DR:
            raise ValueError(f"rate must be one of {sorted(_DR)}")
        if isinstance(bus, int):
            from smbus2 import SMBus
            bus = SMBus(bus)
            self._owns_bus = True
        else:
            self._owns_bus = False
        self._bus = bus
        self.address = address
        self.fsr = fsr
        self.rate = rate
        self._comp = _COMP_DISABLE
        self._lock = threading.RLock()

    # -- low level ---------------------------------------------------------
    def _write(self, reg: int, value: int) -> None:
        self._bus.write_i2c_block_data(self.address, reg, [(value >> 8) & 0xFF, value & 0xFF])

    def _read(self, reg: int) -> int:
        hi, lo = self._bus.read_i2c_block_data(self.address, reg, 2)
        return (hi << 8) | lo

    def _config(self, mux: int) -> int:
        return _OS_START | mux | _PGA[self.fsr] | _MODE_SINGLE | _DR[self.rate] | self._comp

    def _convert(self, mux: int) -> int:
        with self._lock:
            self._write(_REG_CONFIG, self._config(mux))
            # one conversion takes 1/rate seconds; poll the OS bit until done
            time.sleep(1.0 / self.rate + 0.0001)
            for _ in range(100):
                if self._read(_REG_CONFIG) & _OS_START:
                    break
                time.sleep(0.0001)
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
            ValueError: If `channel` is not 0 to 3.
            OSError: If the board does not answer on the I²C bus.
        """
        if channel not in (0, 1, 2, 3):
            raise ValueError("channel must be 0-3")
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
            OSError: If the board does not answer on the I²C bus.
        """
        total = 0
        for _ in range(samples):
            total += self.read_raw(channel)
        return total / samples * self.fsr / 32768

    def read_differential(self, pos: int, neg: int, samples: int = 1) -> float:
        """Read the voltage between two inputs.

        Both inputs must stay between GND and VDD, and both channels' RES jumpers must be open.

        Args:
            pos: Positive input channel.
            neg: Negative input channel. Valid pairs are (0, 1), (0, 3), (1, 3) and (2, 3).
            samples: Number of conversions to average.

        Returns:
            Mean voltage `pos − neg` (V); can be negative.

        Raises:
            ValueError: If the pair is not one the ADS1115 supports.
            OSError: If the board does not answer on the I²C bus.
        """
        if (pos, neg) not in _MUX_DIFF:
            raise ValueError("differential pair must be (0, 1), (0, 3), (1, 3) or (2, 3)")
        total = 0
        for _ in range(samples):
            total += self._convert(_MUX_DIFF[(pos, neg)])
        return total / samples * self.fsr / 32768

    def enable_ready_pin(self) -> None:
        """Make the RDY pin pulse low each time a conversion finishes.

        RDY is J1 pin 5 (the chip's ALERT/RDY pin), pulled up to VDD on the board. Wire it to
        a GPIO and watch for the falling edge. The Qwiic connectors do not carry RDY.
        """
        with self._lock:
            self._write(_REG_HI_THRESH, 0x8000)
            self._write(_REG_LO_THRESH, 0x0000)
            self._comp = _COMP_ASSERT_1

    def start(self, channel: int) -> None:
        """Start a conversion and return at once, without waiting for the result.

        Read the result with [`result_voltage()`][pingoblin_ads1115.ADS1115.result_voltage]
        after the RDY pin pulses, or after `1/rate` seconds.

        Args:
            channel: Channel number, 0 to 3.
        """
        with self._lock:
            self._write(_REG_CONFIG, self._config(_MUX_SINGLE[channel]))

    def result_voltage(self) -> float:
        """Read the result of the last conversion.

        Returns:
            Voltage (V) from the conversion register, scaled by `fsr`.
        """
        with self._lock:
            raw = self._read(_REG_CONVERSION)
        raw = raw - 0x10000 if raw & 0x8000 else raw
        return raw * self.fsr / 32768

    def close(self) -> None:
        """Close the I²C bus if this object opened it (when `bus` was a bus number)."""
        if self._owns_bus:
            self._bus.close()

    def __enter__(self) -> "ADS1115":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def find_boards(bus: int | object = 1, addresses: tuple = ADDRESSES, **kwargs: float) -> "dict[int, ADS1115]":
    """Find every board that answers on the bus.

    Args:
        bus: I²C bus number, or an open bus object shared by all boards found.
        addresses: Addresses to try.
        **kwargs: `fsr` and `rate`, passed to each [`ADS1115`][pingoblin_ads1115.ADS1115].

    Returns:
        Dictionary of address to `ADS1115`, in address order. Empty if none answer.
    """
    if isinstance(bus, int):
        from smbus2 import SMBus
        bus = SMBus(bus)
    found = {}
    for addr in addresses:
        adc = ADS1115(bus, address=addr, **kwargs)
        try:
            adc.read_raw(0)
        except OSError:
            continue
        found[addr] = adc
    return found


__all__ = ["ADS1115", "ADDRESSES", "find_boards"]
