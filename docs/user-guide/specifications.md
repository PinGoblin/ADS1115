# Electrical specifications and safety

Run the board from 2.0–5.5 V and keep every input between 0 V and VDD; the protection is for mistakes, not for continuous use outside these limits.

## Operating conditions

| Parameter | Min | Typical | Max | Unit |
|---|---|---|---|---|
| Supply voltage, VDD | 2.0 | 3.3 | 5.5 | V |
| Supply current, board only (ADC + LED + pull-ups idle) | — | 1.5 | — | mA |
| Sensor supply current, VDD on J2–J5, all headers combined | — | — | 500 | mA |
| Extra current per channel with RES closed | — | — | 0.33 | mA (at 3.3 V) |
| Input voltage for valid readings | 0 | — | VDD | V |
| Sample rate | 8 | 128 | 860 | samples/s |
| I²C clock | — | 100 / 400 | 400 | kHz |
| Operating temperature | −25 | — | 85 | °C (limited by the Qwiic connectors) |

## Absolute maximum ratings

Exceeding these may damage the board.

| Parameter | Limit |
|---|---|
| VDD | −0.3 V to 7 V |
| Brief fault voltage on a sensor SIG pin (series resistor protection) | −20 V to +24 V |
| Continuous voltage on a sensor SIG pin | −0.3 V to VDD + 0.3 V |
| Voltage on I²C and RDY pins | −0.3 V to VDD + 0.3 V |

## Safety and handling

- This is a low-voltage board. Never connect it to mains voltage or to circuits referenced to mains.
- The I²C pull-ups connect to VDD, so the bus runs at the board's supply voltage. Power the board from 3.3 V when it is wired to a Raspberry Pi or an ESP32: their I²C pins are not 5 V tolerant.
- The Qwiic connectors (J6, J7) pass VDD straight through, so a 5 V supply on J1 reaches every board on the chain. This is fine when every board accepts 5 V, such as other PinGoblin boards and Adafruit STEMMA QT boards. SparkFun Qwiic boards are 3.3 V only: if one is on the chain, power the whole chain from 3.3 V.
- A fault voltage on an input pushes a few milliamps into the board's supply. A brief mistake is harmless; fix the wiring before leaving the board powered.
- The board is static-sensitive: handle it by the edges and avoid touching the inputs while unpowered sensors are being connected.
- Disconnect power before closing or cutting solder jumpers.
