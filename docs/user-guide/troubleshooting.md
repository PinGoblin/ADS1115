# Troubleshooting

Most problems come down to I²C wiring, a jumper in the wrong state or a floating input; work through the table from the top.

| Symptom | Likely cause | Fix |
|---|---|---|
| Board not found, and TP5 to TP6 reads 0 V | No supply on VDD, or VDD and GND swapped (the board has no power LED) | Check J1 pins 1 and 2 |
| `i2cdetect` shows nothing | I²C disabled, SDA and SCL swapped, or no common ground | Enable I²C in `raspi-config`; check pins 3 and 5 on the Pi; check GND |
| Board appears at an unexpected address | Address jumpers changed | Check JP1–JP4; exactly one must be closed |
| No address appears after setting 0x4A or 0x4B | JP1 not fully cut, so SDA or SCL is held low | Re-cut JP1 and check it with a multimeter |
| Board still at 0x49 after closing JP3 or JP4 | JP2 is still closed | Remove the solder from JP2 |
| ESP32 I²C errors or missing devices at 400 kHz | Only the board's 10 kΩ pull-ups on the bus, so the edges are too slow | Use `freq=100_000`, or add 2.2–4.7 kΩ pull-ups to 3.3 V |
| Readings jump around with nothing connected | Input is floating (normal) | Connect a sensor, or close the RES jumper to pull the input to VDD |
| Channel reads close to VDD all the time | RES closed with an open-circuit sensor, or a broken sensor wire | Check the sensor and its wiring; open RES if the sensor outputs a voltage |
| Voltage sensor reads too high or wrong | RES jumper closed on a voltage-output channel | Open the RES jumper (remove the solder bridge with solder wick) |
| Thermistor temperature a few degrees out | Wrong Beta value or wrong VDD in the script | Use the datasheet Beta; measure VDD (see [Accuracy and calibration](accuracy.md)) |
| Readings stop at about 3.3 V | Input is at VDD; the ADC cannot read above its supply | Keep inputs below VDD; divide higher voltages before the board |
| Readings stop at 4.096 V on a 5 V board (`adc.clipped` is `True`) | Full-scale range smaller than the input | Use `fsr=6.144` |
| Very noisy readings | Long unshielded leads, or a noisy supply | Twist or shield the cable, average readings, lower the data rate |
| `ModuleNotFoundError` for `pingoblin_ads1115` or `smbus2` | Package missing or wrong virtual environment | Activate the environment and run `pip install "git+https://github.com/PinGoblin/ADS1115#subdirectory=python"` |
| `PermissionError` or `FileNotFoundError` for `/dev/i2c-1` | I²C not enabled, or the user is not in the `i2c` group | Enable I²C with `sudo raspi-config`, then reboot |
| ESP32 `OSError: [Errno 19] ENODEV` | Wrong pins or address | Check SCL = GPIO22 and SDA = GPIO21; run `i2c.scan()` |
| No ready pulses in `ready_pin_fast.py` | RDY not wired to the interrupt pin | Connect J1 pin 5 to GPIO4 |
