# Troubleshooting

Work through the table from the top. Most problems are I²C wiring, a jumper in the wrong state or a floating input.

| Symptom | Likely cause | Fix |
|---|---|---|
| Board not found, and TP5 to TP6 reads 0 V | No supply on VDD (the board has no power LED) | Check the wire from J1 pin 2 to the host's 3.3 V pin, and J1 pin 1 to GND |
| `i2cdetect` shows nothing, or `No answer from the board at 0x48` | I²C disabled, SDA and SCL swapped, or no common ground | Enable I²C with `sudo raspi-config`, check Pi pins 3 and 5, check GND |
| Board appears at an unexpected address | Address jumpers changed | Check JP1–JP4. Exactly one must be closed |
| No address appears after setting 0x4A or 0x4B | JP1 not fully cut, so SDA or SCL is held low | Cut JP1 again and check it with a multimeter |
| Board still at 0x49 after closing JP3 or JP4 | JP2 is still closed | Remove the solder from JP2 |
| ESP32 I²C errors at 400 kHz | Only the board's 10 kΩ pull-ups are on the bus, so the edges are too slow | Use `freq=100_000`, or add 2.2–4.7 kΩ pull-ups from SDA and SCL to 3.3 V |
| Readings jump around with nothing connected | The input is floating | Connect a sensor, or close the RES jumper to pull the input to VDD |
| Channel reads VDD all the time | RES closed with an open-circuit sensor, or a broken sensor wire | Check the sensor and its wiring. Open RES if the sensor outputs a voltage |
| Voltage sensor reads too high | RES jumper closed on a voltage-output channel | Remove the solder bridge from the RES jumper with solder wick |
| Thermistor temperature several degrees out | Wrong Beta value or wrong VDD in the script | Use the datasheet Beta value and measure VDD (see [Accuracy and calibration](accuracy.md)) |
| Readings stop at the supply voltage | The input is at VDD. The ADC cannot read above its supply | Keep inputs below VDD. Divide higher voltages before the board |
| `InputRangeError: CHn is at the ±4.096 V full-scale limit` | The input is beyond the full-scale range | Use the range the message gives, for example `fsr=6.144` on a 5 V board |
| Very noisy readings | Long unshielded leads, or a noisy supply | Twist or shield the cable, average readings or lower the data rate |
| `ModuleNotFoundError` for `pingoblin_ads1115` or `smbus2` | Package missing, or the wrong virtual environment | Activate the environment and run `pip install "git+https://github.com/PinGoblin/ADS1115#subdirectory=python"` |
| `PermissionError` or `FileNotFoundError` for `/dev/i2c-1` | I²C not enabled | Enable I²C with `sudo raspi-config`, then reboot |
| ESP32 `BusError: No answer from the board at 0x48` | Wrong pins or address | Check SCL is GPIO22 and SDA is GPIO21, then run `i2c.scan()` |
| `No ready pulses` from `ready_pin_fast.py` | RDY not wired to the interrupt pin | Connect J1 pin 5 to GPIO4 |
