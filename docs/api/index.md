# ADS1115 API

The repository has two pieces of code, one for each kind of host. Neither needs to be installed as a package: copy the folder you need to your board.

| Folder | Runs on | What it is | Dependencies |
|---|---|---|---|
| [`python/`](https://github.com/PinGoblin/ADS1115/tree/main/python) | Raspberry Pi and other Linux boards | [`breakout_ads`](reference/breakout_ads.md) helper module and six example scripts | Adafruit [`adafruit-circuitpython-ads1x15`](https://pypi.org/project/adafruit-circuitpython-ads1x15/) 2.x or 3.x |
| [`micropython/`](https://github.com/PinGoblin/ADS1115/tree/main/micropython) | ESP32, Raspberry Pi Pico and other MicroPython boards | [`ads1115`](reference/ads1115.md) driver and two example scripts | None |

## Raspberry Pi quick start

Enable I²C with `sudo raspi-config` (Interface Options → I2C), reboot, then:

```bash
i2cdetect -y 1           # the board should appear at 48 (or 49/4a/4b)
python3 -m venv ~/ads-env && source ~/ads-env/bin/activate
pip install adafruit-circuitpython-ads1x15
cd python && python3 01_read_all_channels.py
```

In your own code, keep `breakout_ads.py` in the same folder:

```python
from breakout_ads import open_adc, channel, read_average, resistance_from_voltage, ntc_celsius

ads = open_adc()                       # 0x48, ±4.096 V, 128 samples/s
v = read_average(channel(ads, 0), 16)  # CH0 (J2), volts
print(ntc_celsius(resistance_from_voltage(v, vdd=3.30)))   # with JP5 (RES) closed
```

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

| Setting | Raspberry Pi (`open_adc`) | MicroPython (`ADS1115`) | Recommended |
|---|---|---|---|
| I²C address | `address=0x48` | `address=0x48` | Match the board's address jumper |
| Full-scale range | `gain=1` (±4.096 V) | `fsr=4.096` | ±4.096 V on a 3.3 V board |
| Samples per second | `data_rate=128` | `rate=128` | 128; 8 for calibration and slow sensors |

See [Configuration](../user-guide/configuration.md) for the full gain table and [Accuracy and calibration](../user-guide/accuracy.md) for calibration.
