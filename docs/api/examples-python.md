# Raspberry Pi examples

The scripts in the [`python/`](https://github.com/PinGoblin/ADS1115/tree/main/python) folder. Each one imports the [`pingoblin_ads1115`](reference/pingoblin_ads1115.md) package. Run them with `python3 <script>` inside the virtual environment where the package is installed; press Ctrl+C to stop.

| Script | What it does | Jumper setting |
|---|---|---|
| [`01_read_all_channels.py`](#01_read_all_channelspy) | Prints raw counts and volts for CH0–CH3 | RES open |
| [`02_thermistor_ntc.py`](#02_thermistor_ntcpy) | 10 k NTC temperature with the Beta equation; can measure VDD live on a spare channel | RES closed on the NTC channel |
| [`03_light_and_pot.py`](#03_light_and_potpy) | Potentiometer as a percentage and a bare LDR as resistance and light level | CH0 RES open, CH1 RES closed |
| [`04_multiple_boards.py`](#04_multiple_boardspy) | Finds boards at 0x48–0x4B and reads up to 16 channels | One address jumper per board |
| [`05_csv_logger.py`](#05_csv_loggerpy) | Logs averaged readings to CSV, e.g. `python3 05_csv_logger.py 60 log.csv` | Any |
| [`06_calibrate.py`](#06_calibratepy) | One-point gain calibration, saved to `calibration.json` and applied by the other examples | RES open on the channel being calibrated |

## 01_read_all_channels.py

```python title="python/01_read_all_channels.py"
--8<-- "python/01_read_all_channels.py"
```

## 02_thermistor_ntc.py

```python title="python/02_thermistor_ntc.py"
--8<-- "python/02_thermistor_ntc.py"
```

## 03_light_and_pot.py

```python title="python/03_light_and_pot.py"
--8<-- "python/03_light_and_pot.py"
```

## 04_multiple_boards.py

```python title="python/04_multiple_boards.py"
--8<-- "python/04_multiple_boards.py"
```

## 05_csv_logger.py

```python title="python/05_csv_logger.py"
--8<-- "python/05_csv_logger.py"
```

## 06_calibrate.py

```python title="python/06_calibrate.py"
--8<-- "python/06_calibrate.py"
```
