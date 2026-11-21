# ESP32 / MicroPython

Full documentation, including the API reference: https://pingoblin.github.io/ADS1115/

No extra libraries are needed. Copy `ads1115.py` to the board with Thonny or `mpremote cp ads1115.py :`, then copy the example you want to run (as `main.py` to run it at boot).

| File | What it is |
|---|---|
| `ads1115.py` | Module with no dependencies: single-ended and differential reads, gain and data rate, RDY-pin support |
| `main.py` | Thermistor on CH0 (RES jumper closed) and voltages on CH1–CH3 |
| `ready_pin_fast.py` | 860 samples/s using the RDY pin (J1 pin 5) on GPIO4 as an interrupt |

Default wiring (ESP32 I2C0): SCL = GPIO22, SDA = GPIO21, VDD = 3V3. The Qwiic connectors don't carry RDY: wire J1 pin 5 to a GPIO to use it.

```python
from machine import I2C, Pin
from ads1115 import ADS1115

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400_000)
adc = ADS1115(i2c, address=0x48, fsr=4.096, rate=128)
print(adc.read_voltage(0))
```
