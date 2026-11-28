# User guide

The PinGoblin ADS1115 adds four 16-bit analogue inputs to a Raspberry Pi, ESP32 or any other I²C host, and is built to survive wiring mistakes. It uses the Texas Instruments ADS1115 ADC. PinGoblin's Raspberry Pi and MicroPython libraries drive it directly, and it also works with other ADS1115 libraries.

This user guide covers the hardware. The Python and MicroPython code is in the [API](../api/index.md) section.

## Key features

- **4 single-ended inputs** (or 2 differential pairs), 16-bit, up to 860 samples per second
- **One 3-pin header per channel**: GND, VDD and SIG
- **Protected inputs**: A 4.7 kΩ series resistor on every channel survives a brief connection to ±15 V
- **Resistive sensors without extra parts**: Close a channel's RES jumper to connect a bare thermistor, LDR or force sensor
- **One 2.54 mm host header**: VDD, GND, SCL, SDA and RDY
- **Four I²C addresses**: Up to four boards (16 channels) on one bus
- **Test pads** on every input and bus signal, and four M2.5 mounting holes
- **5 µA idle current**: No power LED, so it suits battery-powered projects
- **Nothing to fit or remove**: Every component is factory-fitted, and options are set with solder jumpers

## Summary specifications

| Specification | Value |
|---|---|
| ADC | TI ADS1115, 16-bit delta-sigma, internal reference |
| Channels | 4 single-ended or 2 differential |
| Sample rate | 8–860 samples/s (programmable) |
| Programmable gain ranges | ±6.144 V, ±4.096 V, ±2.048 V, ±1.024 V, ±0.512 V, ±0.256 V |
| Supply voltage (VDD) | 2.7–5.25 V. 3.3 V with a Raspberry Pi or ESP32 |
| Supply current, board only | 5 µA idle, 300 µA maximum while converting (final figure after prototype testing) |
| Sensor supply (VDD on J2–J5) | 500 mA maximum, all headers combined |
| Input voltage range | 0 V to VDD |
| Interface | I²C, addresses 0x48 (default), 0x49, 0x4A, 0x4B |
| Input series resistor | 4.7 kΩ, 1 % |
| Input filter | 100 nF per channel, 340 Hz corner with the 4.7 kΩ resistor |
| Resistive-sensor excitation | 10 kΩ to VDD, enabled per channel by the RES jumper |
| On-board pull-ups | 10 kΩ on SDA, SCL and RDY |

Full limits are in [Electrical specifications and safety](specifications.md).
