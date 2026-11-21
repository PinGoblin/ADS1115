# Raspberry Pi examples

Full documentation, including the API reference: https://pingoblin.github.io/ADS1115/

Built on the Adafruit [`adafruit-circuitpython-ads1x15`](https://pypi.org/project/adafruit-circuitpython-ads1x15/) library (versions 2.x and 3.x both work). `breakout_ads.py` hides the differences between those versions and holds the board constants and conversion maths, so keep it in the same folder as the scripts.

```bash
sudo raspi-config        # Interface Options -> I2C -> Enable, then reboot
i2cdetect -y 1           # the board should appear at 48 (or 49/4a/4b)
python3 -m venv ~/ads-env && source ~/ads-env/bin/activate
pip install adafruit-circuitpython-ads1x15
python3 01_read_all_channels.py
```

| Script | What it shows | Jumpers |
|---|---|---|
| `breakout_ads.py` | Module used by every script: library setup, board constants, conversion maths, calibration | — |
| `01_read_all_channels.py` | Raw counts and volts on CH0–CH3 | RES open |
| `02_thermistor_ntc.py` | 10 k NTC temperature (Beta equation), optional live VDD measurement | RES closed on the NTC channel |
| `03_light_and_pot.py` | Two sensor types side by side: potentiometer (%) and bare LDR | CH0 RES open, CH1 RES closed |
| `04_multiple_boards.py` | Finds up to four boards (0x48–0x4B) and reads 16 channels | One address jumper per board |
| `05_csv_logger.py` | Logs all channels to CSV: `python3 05_csv_logger.py 60 log.csv` | Any |
| `06_calibrate.py` | One-point gain calibration saved to `calibration.json` | RES open on the channel being calibrated |

## Module functions (`breakout_ads.py`)

| Function | Purpose |
|---|---|
| `open_adc(address=0x48, gain=1, data_rate=128)` | Opens the board on I²C bus 1 |
| `channel(ads, ch, ch_neg=None)` | Input CH0–CH3, or a differential pair with `ch_neg` |
| `read_average(chan, samples=8)` | Averaged voltage |
| `resistance_from_voltage(v_adc, vdd=VDD_NOMINAL)` | Sensor resistance with the RES jumper closed: `10k × V / (VDD − V)` |
| `ntc_celsius(r_ntc, r0=10000, t0_c=25, beta=3950)` | Thermistor temperature (Beta equation) |
| `percent_of_range(v_adc, v_min=0, v_max=VDD_NOMINAL)` | Voltage as a percentage of a range |
| `load_calibration(path=None)`, `apply_calibration(v_adc, ch, cal)`, `save_calibration(cal, path=None)` | Per-channel gain correction |

Resistive-sensor maths uses VDD, so measure your actual 3.3 V rail and set `VDD_NOMINAL`, or let `02_thermistor_ntc.py` measure it on a spare channel.
