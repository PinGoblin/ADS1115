# Troubleshooting

Most problems come down to I²C wiring, a jumper in the wrong state or a floating input; work through the table from the top.

| Symptom | Likely cause | Fix |
|---|---|---|
| Power LED off | No supply on VDD, or VDD and GND swapped | Check J1 pins 1 and 2 or the Qwiic cable; measure TP5 to TP6 |
| `i2cdetect` shows nothing | I²C disabled, SDA and SCL swapped, or no common ground | Enable I²C in `raspi-config`; check pins 3 and 5 on the Pi; check GND |
| Board appears at an unexpected address | Address jumpers changed | Check JP1–JP4; exactly one must be closed |
| No address appears after changing the address | JP1 not fully cut, so two jumpers are closed | Re-cut JP1 and check it with a multimeter |
| Readings jump around with nothing connected | Input is floating (normal) | Connect a sensor, or close the RES jumper to pull the input to VDD |
| Channel reads close to VDD all the time | RES closed with an open-circuit sensor, or a broken sensor wire | Check the sensor and its wiring; open RES if the sensor outputs a voltage |
| Voltage sensor reads too high or wrong | RES jumper closed on a voltage-output channel | Open the RES jumper (remove the solder bridge with solder wick) |
| Thermistor temperature a few degrees out | Wrong Beta value or wrong VDD in the script | Use the datasheet Beta; measure VDD (see [Accuracy and calibration](accuracy.md)) |
| Readings stop at about 3.3 V | Input is at VDD; the ADC cannot read above its supply | Keep inputs below VDD; divide higher voltages before the board |
| Very noisy readings | Long unshielded leads, or a noisy supply | Twist or shield the cable, average readings, lower the data rate |
| `ModuleNotFoundError` for `pingoblin_ads1115` or `smbus2` | Package missing or wrong virtual environment | Activate the environment and run `pip install "git+https://github.com/PinGoblin/ADS1115#subdirectory=python"` |
| `PermissionError` or `FileNotFoundError` for `/dev/i2c-1` | I²C not enabled, or the user is not in the `i2c` group | Enable I²C with `sudo raspi-config`, then reboot |
| ESP32 `OSError: [Errno 19] ENODEV` | Wrong pins or address | Check SCL = GPIO22 and SDA = GPIO21; run `i2c.scan()` |
| No ready pulses in `ready_pin_fast.py` | RDY not wired to the interrupt pin | Connect J1 pin 5 to GPIO4 |
