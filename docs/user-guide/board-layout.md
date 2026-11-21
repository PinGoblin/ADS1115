# Board layout and pinouts

The host connects through J1 or either Qwiic connector; each sensor gets its own 3-pin header. All three host connectors are wired in parallel, so use whichever suits your project.

## J1 — host header (1×5, 2.54 mm)

| Pin | Signal | Connect to |
|---|---|---|
| 1 | VDD | 3.3 V supply from the host (2.0–5.5 V allowed) |
| 2 | GND | Host ground |
| 3 | SCL | I²C clock |
| 4 | SDA | I²C data |
| 5 | RDY (the ADC's ALERT/RDY pin) | Optional: a GPIO input for conversion-ready or threshold alerts |

## J6, J7 — Qwiic / STEMMA QT (JST-SH, 4-pin)

Pin 1 GND, pin 2 VDD (the board's supply, 3.3 V or 5 V), pin 3 SDA, pin 4 SCL. Plug a cable into either one; the other passes the bus on to the next Qwiic device.

## J2–J5 — sensor headers (1×3, 2.54 mm, one per channel)

| Header | Channel | Pin 1 | Pin 2 | Pin 3 |
|---|---|---|---|---|
| J2 | CH0 (A0) | GND | VDD | SIG |
| J3 | CH1 (A1) | GND | VDD | SIG |
| J4 | CH2 (A2) | GND | VDD | SIG |
| J5 | CH3 (A3) | GND | VDD | SIG |

!!! warning "VDD on the sensor headers is a supply output"
    It is the board's own supply (whatever J1 or the Qwiic cable provides) and is there to power the sensor. Never connect an external supply to it: a 5 V sensor's supply goes to your 5 V source, and only its GND and SIG go to the header. Keep the total load across all four headers to 500 mA or less, and within what your host's 3.3 V supply can provide. That is plenty for sensor modules, but not for motors, relays or gas-sensor heaters.

## Solder jumpers

| Jumper | Default | Function |
|---|---|---|
| JP1 | Closed (trace) | I²C address 0x48 (ADDR to GND) |
| JP2 | Open | I²C address 0x49 (ADDR to VDD) |
| JP3 | Open | I²C address 0x4A (ADDR to SDA) |
| JP4 | Open | I²C address 0x4B (ADDR to SCL) |
| JP5–JP8 (RES) | Open | Close to enable the 10 kΩ excitation resistor on CH0–CH3 for resistive sensors |

## Test pads and other parts

**Test pads (1.5 mm)**: TP1–TP4 on the ADC side of each input (AIN0–AIN3), TP5 VDD, TP6 GND, TP7 SDA, TP8 SCL, TP9 RDY.

**Other**: D1 power LED (red, about 1.3 mA); H1–H4 M2.5 mounting holes (2.7 mm, unplated, not connected).

## Dimensions

![Engineering drawing of the board: holes and connector centres dimensioned from the left and bottom edges](images/board-dimensions.png)

*Top view. All dimensions in mm, from the left edge (datum A) and bottom edge (datum B) to feature centres.*
