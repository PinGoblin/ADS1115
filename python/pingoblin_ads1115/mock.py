"""A simulated I²C bus with PinGoblin ADS1115 boards on it, for running code without hardware.

Every example accepts `--mock` and then uses this bus instead of I²C bus 1.
"""
from __future__ import annotations

_FSR = (6.144, 4.096, 2.048, 1.024, 0.512, 0.256, 0.256, 0.256)
_DIFF = {0: (0, 1), 1: (0, 3), 2: (1, 3), 3: (2, 3)}

DEFAULT_VOLTS = (1.65, 1.65, 2.5, 3.0)
"""Input voltages of a simulated board, CH0–CH3 (V): Half of 3.3 V on CH0 and CH1 (a 10 kΩ sensor
at 25 °C with the RES jumper closed, or a potentiometer at its centre), 2.5 V and 3.0 V."""


class MockBus:
    """A simulated I²C bus with one or more boards on it.

    Pass it to [`ADS1115`][pingoblin_ads1115.ADS1115] or
    [`find_boards()`][pingoblin_ads1115.find_boards] in place of a bus number. Each simulated
    board answers like a real one: Conversions use the range and channel you set, readings
    beyond the range reach full scale, and an address with no board raises `OSError`.

    Example:
        ```python
        from pingoblin_ads1115 import ADS1115, MockBus

        bus = MockBus()
        bus.volts[0x48][2] = 0.75            # CH2 of the board at 0x48 now reads 0.75 V
        print(ADS1115(bus).read_voltage(2))
        ```

    Args:
        volts: Input voltages CH0–CH3 (V), the same on every simulated board.
        addresses: I²C addresses of the simulated boards.

    Attributes:
        volts (dict[int, list[float]]): Input voltages CH0–CH3 of each board, by address.
            Change them to simulate a sensor.
    """

    def __init__(self, volts: tuple = DEFAULT_VOLTS, addresses: tuple = (0x48,)):
        self.volts = {addr: list(volts) for addr in addresses}
        self._regs = {addr: {0: 0x0000, 1: 0x8583, 2: 0x8000, 3: 0x7FFF} for addr in addresses}

    def _board(self, address: int) -> dict:
        if address not in self._regs:
            raise OSError(121, "Remote I/O error")
        return self._regs[address]

    def write_i2c_block_data(self, address: int, register: int, data: list) -> None:
        """Write a 16-bit register of the simulated board at `address`.

        Args:
            address: I²C address.
            register: Register number, 0 to 3.
            data: Two bytes, most significant first.

        Raises:
            OSError: If no simulated board has that address.
        """
        regs = self._board(address)
        value = (data[0] << 8) | data[1]
        if register == 1 and value & 0x8000:
            mux, fsr = (value >> 12) & 7, _FSR[(value >> 9) & 7]
            volts = self.volts[address]
            v = volts[mux - 4] if mux >= 4 else volts[_DIFF[mux][0]] - volts[_DIFF[mux][1]]
            regs[0] = max(-32768, min(32767, round(v / fsr * 32768))) & 0xFFFF
        if register != 0:
            regs[register] = value

    def read_i2c_block_data(self, address: int, register: int, length: int) -> list:
        """Read a 16-bit register of the simulated board at `address`.

        Args:
            address: I²C address.
            register: Register number, 0 to 3.
            length: Number of bytes, always 2.

        Returns:
            Two bytes, most significant first. Conversions finish at once.

        Raises:
            OSError: If no simulated board has that address.
        """
        value = self._board(address)[register]
        return [value >> 8, value & 0xFF][:length]

    def close(self) -> None:
        """Do nothing: A simulated bus has nothing to close."""


__all__ = ["DEFAULT_VOLTS", "MockBus"]
