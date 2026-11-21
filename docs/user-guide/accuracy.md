# Accuracy and calibration

Uncalibrated, expect about ±0.3 % of reading on voltage inputs; a one-point calibration brings this close to the ADC's own limit. For resistive sensors, knowing the real VDD matters more than anything else.

| Error source | Typical size | How to reduce it |
|---|---|---|
| 4.7 kΩ series resistor against the ADC's input impedance | About 0.1 % low at ±4.096 V; up to about 0.7 % at ±0.256 V | One-point calibration (`06_calibrate.py`) |
| ADS1115 gain and offset error | About 0.01 % typical, 0.15 % maximum | One-point calibration |
| Unknown VDD (resistive sensors only) | 1 % VDD error gives about 0.3–0.5 °C on a 10 k NTC at room temperature | Measure VDD at TP5–TP6, or measure it live on a spare channel |
| 10 kΩ excitation resistor tolerance (1 %) | About 0.25 °C on a 10 k NTC | Calibrate against a reference thermometer |
| Thermistor tolerance and Beta value | ±0.2 to ±1 °C, depending on the part | Use the exact datasheet Beta value or a Steinhart–Hart fit |
| Noise | A few counts at 128 samples/s | Average readings, or lower the data rate |

## One-point voltage calibration

1. Leave the channel's RES jumper open.
2. Link the channel header's VDD pin to its SIG pin with a jumper wire.
3. Measure the voltage at that header with a good multimeter.
4. Run `python3 06_calibrate.py <channel> <volts>`, for example `python3 06_calibrate.py 0 3.297`.
5. Repeat for each channel. The examples apply the stored factors automatically.

## Measuring VDD live

Link a spare channel's VDD pin to its SIG pin (RES open) and set `VDD_CHANNEL` in `02_thermistor_ntc.py`. The script then uses the measured supply for every reading, which also tracks supply drift.

## Temperature calibration

For the best thermistor accuracy, place the thermistor next to a trusted thermometer at a temperature in the middle of your range and adjust `BETA` or `R0` until the readings agree.
