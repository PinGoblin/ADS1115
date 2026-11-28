# User guide

This board adds four 16-bit analogue inputs to a Raspberry Pi, ESP32 or any other I²C host, and is built to survive wiring mistakes. It uses the Texas Instruments ADS1115 ADC. PinGoblin's Raspberry Pi and MicroPython libraries drive it directly, and it also works with other ADS1115 libraries.

This user guide covers the board hardware: pinouts, wiring, sensors, configuration, accuracy, specifications and troubleshooting. The Python and MicroPython code is described in the [API](../api/index.md) section.

## Key features

- **4 single-ended inputs** (or 2 differential pairs), 16-bit, up to 860 samples per second
- **Plug-and-play sensor headers**: one 3-pin header (GND, VDD, SIG) per channel
- **Protected inputs**: a 4.7 kΩ series resistor on every channel survives an accidental connection to ±15 V
- **Resistive sensors without extra parts**: close a channel's RES jumper to connect a bare thermistor, LDR or force sensor
- **One 2.54 mm header for the host** (VDD, GND, SCL, SDA, RDY)
- **Four I²C addresses**: up to four boards (16 channels) on one bus
- **Test pads** on every input and bus signal, and four M2.5 mounting holes
- **Under 5 µA when idle**: no power LED, so it suits battery-powered projects
- **Nothing to fit or remove**: every component is factory-fitted; options are set with solder jumpers

## Summary specifications

| Specification | Value |
|---|---|
| ADC | TI ADS1115, 16-bit delta-sigma, internal reference |
| Channels | 4 single-ended or 2 differential |
| Sample rate | 8 to 860 samples/s (programmable) |
| Programmable gain ranges | ±6.144, ±4.096, ±2.048, ±1.024, ±0.512, ±0.256 V |
| Supply voltage (VDD) | 2.7 to 5.25 V (use 3.3 V with a Raspberry Pi or ESP32) |
| Supply current | Under 5 µA idle, 300 µA max while converting (sensors not included) |
| Sensor supply (VDD on J2–J5) | 500 mA max, all headers combined (and within your host's 3.3 V supply) |
| Input voltage range | 0 V to VDD |
| Interface | I²C, addresses 0x48 (default), 0x49, 0x4A, 0x4B |
| Input series resistor | 4.7 kΩ, 1 % |
| Input filter | 100 nF per channel (about 340 Hz corner with 4.7 kΩ) |
| Resistive-sensor excitation | 10 kΩ to VDD, enabled per channel by the RES jumper |
| On-board I²C pull-ups | 10 kΩ on SDA, SCL and RDY |

Full limits are in [Electrical specifications and safety](specifications.md).
