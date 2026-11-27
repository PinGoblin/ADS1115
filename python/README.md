# Raspberry Pi library and examples

Full documentation, including the API reference: https://pingoblin.github.io/ADS1115/

The `pingoblin_ads1115` package talks to the ADS1115 directly with [`smbus2`](https://pypi.org/project/smbus2/). It has the same methods as the MicroPython `ads1115` module, is thread-safe, and works with any ADS1115 breakout.

```bash
sudo raspi-config        # Interface Options -> I2C -> Enable, then reboot
i2cdetect -y 1           # the board should appear at 48 (or 49/4a/4b)
python3 -m venv ~/ads-env && source ~/ads-env/bin/activate
pip install "git+https://github.com/PinGoblin/ADS1115#subdirectory=python"
python3 01_read_all_channels.py
```

| Script | What it shows | Jumpers |
|---|---|---|
| `01_read_all_channels.py` | Raw counts and volts on CH0–CH3 | RES open |
| `02_thermistor_ntc.py` | 10 k NTC temperature (Beta equation), optional live VDD measurement | RES closed on the NTC channel |
| `03_light_and_pot.py` | Two sensor types side by side: potentiometer (%) and bare LDR | CH0 RES open, CH1 RES closed |
| `04_multiple_boards.py` | Finds up to four boards (0x48–0x4B) and reads 16 channels | One address jumper per board |
| `05_csv_logger.py` | Logs all channels to CSV: `python3 05_csv_logger.py 60 log.csv` | Any |
| `06_calibrate.py` | One-point gain calibration saved to `calibration.json` | RES open on the channel being calibrated |

## Package contents (`pingoblin_ads1115`)

| Name | Purpose |
|---|---|
| `ADS1115(bus=1, address=0x48, fsr=4.096, rate=128)` | One board on I²C bus 1 |
| `adc.read_voltage(ch, samples=1)`, `adc.read_raw(ch)` | Single-ended reading in volts or counts |
| `adc.read_differential(pos, neg, samples=1)` | Voltage between two inputs |
| `adc.enable_ready_pin()`, `adc.start(ch)`, `adc.result_voltage()` | Conversions signalled by the RDY pin |
| `find_boards(bus=1)` | Every board that answers at 0x48–0x4B |
| `resistance_from_voltage(v_adc, vdd=VDD_NOMINAL)` | Sensor resistance with the RES jumper closed: `10k × V / (VDD − V)` |
| `ntc_celsius(r_ntc, r0=10000, t0_c=25, beta=3950)` | Thermistor temperature (Beta equation) |
| `percent_of_range(v_adc, v_min=0, v_max=VDD_NOMINAL)` | Voltage as a percentage of a range |
| `load_calibration(path=None)`, `apply_calibration(v_adc, ch, cal)`, `save_calibration(cal, path=None)` | Per-channel gain correction, stored in `calibration.json` in the working directory |

Resistive-sensor maths uses VDD, so measure your actual 3.3 V rail and pass it as `vdd`, or let `02_thermistor_ntc.py` measure it on a spare channel.
