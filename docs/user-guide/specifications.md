# Electrical specifications and safety

Run the board from 2.7–5.25 V and keep every input between 0 V and VDD; the protection is for mistakes, not for continuous use outside these limits.

## Operating conditions

| Parameter | Min | Typical | Max | Unit |
|---|---|---|---|---|
| Supply voltage, VDD | 2.7 | 3.3 | 5.25 | V |
| Supply current, board only, idle (ADC powered down between readings) | — | 0.5 | 5 | µA |
| Supply current, board only, while converting | — | 150 | 300 | µA |
| Sensor supply current, VDD on J2–J5, all headers combined | — | — | 500 | mA |
| Extra current per channel with RES closed | — | — | 0.33 | mA (at 3.3 V) |
| Input voltage for valid readings | 0 | — | VDD | V |
| Sample rate | 8 | 128 | 860 | samples/s |
| I²C clock, using only the board's 10 kΩ pull-ups (e.g. ESP32) | — | 100 | 100 | kHz |
| I²C clock with 2.2–4.7 kΩ host pull-ups (the Raspberry Pi has 1.8 kΩ) | — | 100 / 400 | 400 | kHz |
| Operating temperature | −40 | — | 85 | °C |

## Absolute maximum ratings

Exceeding these may damage the board.

| Parameter | Limit |
|---|---|
| VDD | −0.3 V to 5.5 V |
| Brief fault voltage on a sensor SIG pin (series resistor protection) | −15 V to +15 V |
| Continuous voltage on a sensor SIG pin | −0.3 V to VDD + 0.3 V |
| Voltage on I²C and RDY pins | −0.3 V to 5.5 V |

The ADS1115 itself runs from 2.0 V, but below 2.7 V the I²C logic margins are small and no Raspberry Pi or ESP32 runs its bus that low. VDD is limited to 5.5 V (not the chip's 7 V) because the on-board pull-ups connect SDA, SCL and RDY to VDD, and those pins are rated to 5.5 V.

## Safety and handling

- This is a low-voltage board. Never connect it to mains voltage or to circuits referenced to mains.
- The I²C pull-ups connect to VDD, so the bus runs at the board's supply voltage. Power the board from 3.3 V when it is wired to a Raspberry Pi or an ESP32: their I²C pins are not 5 V tolerant.
- A fault voltage on an input pushes up to about 4 mA per channel into the board's supply. A brief mistake is harmless when the board runs from a Raspberry Pi or ESP32 3.3 V pin, because the host's own load absorbs it. A supply with very little other load (for example a small regulator powering only this board) cannot absorb it, and its voltage can rise. Fix the wiring before leaving the board powered.
- Connect and disconnect J1 with the power off.
- The board is static-sensitive: handle it by the edges and avoid touching the inputs while unpowered sensors are being connected.
- Disconnect power before closing or cutting solder jumpers.
