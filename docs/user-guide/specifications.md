# Electrical specifications and safety

Run the PinGoblin ADS1115 from 2.7–5.25 V, and keep every input between 0 V and VDD. The input protection is for mistakes, not for continuous use outside these limits.

## Safety rules

- **Never connect the board to mains voltage or to circuits referenced to mains.**
- **Never power the board from 5 V when it is wired to a Raspberry Pi or ESP32.** Their I²C pins are 3.3 V only.
- **Never swap VDD and GND.** The board has no reverse-polarity protection.
- **Never connect a supply to VDD on a sensor header (J2–J5).** It is the board's supply output.
- **Never draw more than 500 mA from the sensor headers, or short a header's VDD to GND.** The sensor supply has no fuse: It comes straight from the host's 3.3 V pin, and a short or an overload pulls that supply down and resets the host.
- **Never put more than 5.5 V on VDD, or more than ±15 V on a SIG pin.**
- **Connect and disconnect J1 with the power off.**
- **Disconnect power before closing or cutting solder jumpers.**
- Handle the board by its edges. It is static-sensitive.

## Which host pin to use

VDD must equal the host's I²C voltage.

| Host | Connect J1 pin 2 (VDD) to | Never connect it to |
|---|---|---|
| Raspberry Pi (all 40-pin models) | Pin 1 or pin 17 (3V3) | Pin 2 or pin 4 (5V) |
| ESP32 DevKit | 3V3 | 5V or VIN |
| Raspberry Pi Pico | Pin 36 (3V3 OUT) | Pin 39 (VSYS) or pin 40 (VBUS) |

## Current budget

The host's 3.3 V pin supplies everything below. Add the rows that apply and check the total against your host's 3.3 V rating. A Raspberry Pi's 3V3 pins are for low-current peripherals.

| Load | Current at 3.3 V |
|---|---|
| Board, idle | 5 µA (final figure after prototype testing) |
| Board, while converting | 300 µA maximum |
| Each channel with its RES jumper closed | 0.33 mA maximum (sensor shorted) |
| Sensors powered from J2–J5 | Your sensors' own current. 500 mA maximum, all headers combined, and within your host's 3.3 V rating. No fuse |
| SDA, SCL and RDY pulled low | 0.33 mA each, only while low |

## Operating conditions

| Parameter | Min | Typical | Max | Unit |
|---|---|---|---|---|
| Supply voltage, VDD | 2.7 | 3.3 | 5.25 | V |
| Supply current, board only, idle | — | 0.5 | 5 | µA |
| Supply current, board only, while converting | — | 150 | 300 | µA |
| Sensor supply current, VDD on J2–J5, all headers combined | — | — | 500 | mA |
| Extra current per channel with RES closed, at 3.3 V | — | — | 0.33 | mA |
| Input voltage for valid readings | 0 | — | VDD | V |
| Sample rate | 8 | 128 | 860 | samples/s |
| I²C clock, board pull-ups only (ESP32, Pico) | — | 100 | 100 | kHz |
| I²C clock with 2.2–4.7 kΩ host pull-ups (the Raspberry Pi has 1.8 kΩ) | — | 100 | 400 | kHz |
| Operating temperature | −40 | — | 85 | °C |

Supply current figures are the ADS1115's datasheet values (final figures after prototype testing).

## Absolute maximum ratings

Exceeding these can damage the board.

| Parameter | Limit |
|---|---|
| VDD | −0.3 V to 5.5 V |
| Brief fault voltage on a sensor SIG pin | −15 V to +15 V (final figure after prototype testing) |
| Continuous voltage on a sensor SIG pin | −0.3 V to VDD + 0.3 V |
| Voltage on SDA, SCL and RDY | −0.3 V to 5.5 V |

VDD is limited to 5.5 V because the on-board pull-ups connect SDA, SCL and RDY to VDD, and those pins are rated to 5.5 V. The ADS1115 runs from 2.0 V, but below 2.7 V the I²C logic margins are small, and no Raspberry Pi or ESP32 runs its bus that low.

## Fault current

A fault voltage on a SIG pin pushes up to 4 mA per channel into the board's supply. The host's own load absorbs it when the board runs from a Raspberry Pi or ESP32 3.3 V pin. A supply with almost no other load, such as a small regulator powering only this board, cannot absorb it, and its voltage rises. Fix the wiring before leaving the board powered.
