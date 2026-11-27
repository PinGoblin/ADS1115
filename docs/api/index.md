# ADS1115 API

The repository has one library for each kind of host, with the same methods on both, and example scripts for each.

| Folder | Runs on | What it is | Dependencies |
|---|---|---|---|
| [`python/`](https://github.com/PinGoblin/ADS1115/tree/main/python) | Raspberry Pi and other Linux boards | [`pingoblin_ads1115`](reference/pingoblin_ads1115.md) package, which talks to the chip directly, and [six example scripts](examples-python.md) | [`smbus2`](https://pypi.org/project/smbus2/), installed automatically |
| [`micropython/`](https://github.com/PinGoblin/ADS1115/tree/main/micropython) | ESP32, Raspberry Pi Pico and other MicroPython boards | [`ads1115`](reference/ads1115.md) module, which talks to the chip directly, and [two example scripts](examples-micropython.md) | None |

## Raspberry Pi quick start

Enable I²C with `sudo raspi-config` (Interface Options → I2C), reboot, then:

```bash
i2cdetect -y 1           # the board should appear at 48 (or 49/4a/4b)
python3 -m venv ~/ads-env && source ~/ads-env/bin/activate
pip install "git+https://github.com/PinGoblin/ADS1115#subdirectory=python"
```

Then, in your own code:

```python
from pingoblin_ads1115 import ADS1115, resistance_from_voltage, ntc_celsius

adc = ADS1115(address=0x48)                 # I²C bus 1, ±4.096 V, 128 samples/s
v = adc.read_voltage(0, samples=16)         # CH0 (J2), volts
print(ntc_celsius(resistance_from_voltage(v, vdd=3.30)))   # with JP5 (RES) closed
```

To run the examples, copy the [`python`](https://github.com/PinGoblin/ADS1115/tree/main/python) folder to the Pi and run `python3 01_read_all_channels.py` inside it.

The Raspberry Pi library is thread-safe: several threads can share one board, because only one conversion runs at a time. The [PinGoblin dual DC motor board](https://pingoblin.github.io/DRV8874/) library uses it to read motor current.

## MicroPython quick start

Copy `ads1115.py` to the board with Thonny or `mpremote cp ads1115.py :`, then:

```python
from machine import I2C, Pin
from ads1115 import ADS1115

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400_000)   # ESP32 defaults
adc = ADS1115(i2c, address=0x48, fsr=4.096, rate=128)
print([adc.read_voltage(ch) for ch in range(4)])
```

## Choosing settings

Both libraries take the same arguments:

| Setting | Argument | Recommended |
|---|---|---|
| I²C address | `address=0x48` | Match the board's address jumper |
| Full-scale range | `fsr=4.096` | ±4.096 V on a 3.3 V board |
| Samples per second | `rate=128` | 128; 8 for calibration and slow sensors |
| I²C bus (Raspberry Pi only) | `bus=1` | 1, the Pi's header I²C bus |

See [Configuration](../user-guide/configuration.md) for the full range table and [Accuracy and calibration](../user-guide/accuracy.md) for calibration.

## Conversion formulas

Vadc is the voltage the ADC reports. For a resistive sensor with the RES jumper closed, the sensor's resistance is ([`resistance_from_voltage()`][pingoblin_ads1115.resistance_from_voltage]):

```text
Rs = 10 kΩ × Vadc / (VDD − Vadc)
```

For an NTC thermistor, temperature in kelvin follows from the Beta equation ([`ntc_celsius()`][pingoblin_ads1115.ntc_celsius]), using R0, T0 and B from the thermistor's datasheet (commonly 10 kΩ, 298.15 K and 3950):

```text
1/T = 1/T0 + ln(Rs / R0) / B
```

Subtract 273.15 to convert kelvin to degrees Celsius. For voltage-output sensors, use the sensor's own datasheet formula on Vadc directly.
