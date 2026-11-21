# Software and examples

The board works with the Adafruit ADS1x15 libraries for Python, CircuitPython and Arduino, and with the small MicroPython driver supplied with the examples. Ten example files cover the common jobs. Their source code and the full function reference are in the [API](../api/index.md) section.

## Raspberry Pi

Folder [`python/`](https://github.com/PinGoblin/ADS1115/tree/main/python); Adafruit library 2.x or 3.x.

| File | What it does | Jumper setting |
|---|---|---|
| `breakout_ads.py` | Helper used by every example: library setup, board constants, conversion maths, calibration | — |
| `01_read_all_channels.py` | Prints raw counts and volts for CH0–CH3 | RES open |
| `02_thermistor_ntc.py` | 10 k NTC temperature with the Beta equation; can measure VDD live on a spare channel | RES closed on the NTC channel |
| `03_light_and_pot.py` | Potentiometer as a percentage and a bare LDR as resistance and light level | CH0 RES open, CH1 RES closed |
| `04_multiple_boards.py` | Finds boards at 0x48–0x4B and reads up to 16 channels | One address jumper per board |
| `05_csv_logger.py` | Logs averaged readings to CSV, e.g. `python3 05_csv_logger.py 60 log.csv` | Any |
| `06_calibrate.py` | One-point gain calibration, saved to `calibration.json` and applied by the other examples | RES open on the channel being calibrated |

## ESP32 and other MicroPython boards

Folder [`micropython/`](https://github.com/PinGoblin/ADS1115/tree/main/micropython); no extra libraries needed.

| File | What it does |
|---|---|
| `ads1115.py` | Driver with no dependencies: single-ended, differential and ready-pin reads |
| `main.py` | Thermistor on CH0 plus voltages on CH1–CH3 |
| `ready_pin_fast.py` | Samples at 860 per second using the RDY pin (J1 pin 5 to GPIO4) as an interrupt |

## Conversion formulas

Vadc is the voltage the ADC reports. For a resistive sensor with the RES jumper closed, the sensor's resistance is:

```text
Rs = 10 kΩ × Vadc / (VDD − Vadc)
```

For an NTC thermistor, temperature in kelvin follows from the Beta equation, using R0, T0 and B from the thermistor's datasheet (commonly 10 kΩ, 298.15 K and 3950):

```text
1/T = 1/T0 + ln(Rs / R0) / B
```

Subtract 273.15 to convert kelvin to degrees Celsius. For voltage-output sensors, use the sensor's own datasheet formula on Vadc directly.
