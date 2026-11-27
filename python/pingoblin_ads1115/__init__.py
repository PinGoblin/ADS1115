"""Raspberry Pi library for the PinGoblin ADS1115 4-channel 16-bit ADC board.

Talks to the ADS1115 directly with [`smbus2`](https://pypi.org/project/smbus2/), and has the
same methods as the MicroPython `ads1115` module. It also works with any other ADS1115
breakout.

Install on the Pi, in a virtual environment:

```bash
pip install "git+https://github.com/PinGoblin/ADS1115#subdirectory=python"
```

| Name | Purpose |
|---|---|
| [`ADS1115`][pingoblin_ads1115.ADS1115] | One board: single-ended and differential reads, range, data rate, RDY pin |
| [`find_boards()`][pingoblin_ads1115.find_boards] | Finds every board on the bus (0x48–0x4B) |
| [`resistance_from_voltage()`][pingoblin_ads1115.resistance_from_voltage] | Resistive sensor resistance with the RES jumper closed |
| [`ntc_celsius()`][pingoblin_ads1115.ntc_celsius] | Thermistor temperature (Beta equation) |
| [`percent_of_range()`][pingoblin_ads1115.percent_of_range] | Voltage as a percentage of a range |
| [`load_calibration()`][pingoblin_ads1115.load_calibration], [`apply_calibration()`][pingoblin_ads1115.apply_calibration], [`save_calibration()`][pingoblin_ads1115.save_calibration] | Per-channel gain correction |
"""
from .ads1115 import ADDRESSES, ADS1115, find_boards
from .convert import (ADDRESS_JUMPERS, CAL_FILE, R_EXCITATION, R_SERIES, VDD_NOMINAL,
                      apply_calibration, load_calibration, ntc_celsius, percent_of_range,
                      resistance_from_voltage, save_calibration)

__version__ = "1.0.0"

__all__ = ["ADS1115", "ADDRESSES", "ADDRESS_JUMPERS", "CAL_FILE", "R_EXCITATION", "R_SERIES",
           "VDD_NOMINAL", "apply_calibration", "find_boards", "load_calibration", "ntc_celsius",
           "percent_of_range", "resistance_from_voltage", "save_calibration"]
