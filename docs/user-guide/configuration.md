# Configuration

Solder jumpers set the I²C address and each channel's RES mode. Software sets the full-scale range and the data rate.

**Working with solder jumpers.** Disconnect power first. To close a jumper, heat both pads with a soldering iron and add a small blob of solder so it bridges them. To open JP1, cut the thin copper trace between its pads with a sharp craft knife, then check with a multimeter that the pads are no longer connected. Re-solder JP1 to restore the default.

## I²C address

Close exactly one address jumper.

| Address | JP1 (GND) | JP2 (VDD) | JP3 (SDA) | JP4 (SCL) |
|---|---|---|---|---|
| 0x48 (default) | ✓ Closed | ✗ Open | ✗ Open | ✗ Open |
| 0x49 | ✗ Cut | ✓ Closed | ✗ Open | ✗ Open |
| 0x4A | ✗ Cut | ✗ Open | ✓ Closed | ✗ Open |
| 0x4B | ✗ Cut | ✗ Open | ✗ Open | ✓ Closed |

- **0x49 with JP1 still closed:** Nothing is damaged, because JP1 connects through a 10 kΩ resistor, and the board answers at 0x49.
- **0x4A or 0x4B with JP1 still closed:** The bus stops working. Cut JP1.
- **Order for several boards:** 0x48, 0x49, 0x4B, then 0x4A. Address 0x4A connects ADDR to SDA, which relies on the host holding SDA steady for 100 ns after each clock edge. TI recommends using it last.

## Several boards on one bus

Give each board a different address and wire pins 1–4 of every board's J1 (GND, VDD, SCL, SDA) in parallel. Example [`04_multiple_boards.py`](../api/examples-python.md#04_multiple_boardspy) finds and reads all of them. To use RDY, wire each board's J1 pin 5 to its own GPIO. The examples poll instead, so RDY is optional.

| Host | Boards on one bus | I²C clock |
|---|---|---|
| Raspberry Pi (1.8 kΩ pull-ups on the Pi) | Up to 4, counting every other device that has 10 kΩ pull-ups | 100 kHz or 400 kHz |
| ESP32, Raspberry Pi Pico (no pull-ups on the host) | Up to 4 | 100 kHz. 400 kHz needs 2.2–4.7 kΩ resistors from SDA and SCL to 3.3 V at the host |

Each board adds 10 kΩ pull-ups on SDA and SCL. More than four sets on a Raspberry Pi bus need more than 3 mA to pull the bus low, which is more than the I²C devices are rated for.

## RES jumpers

JP5–JP8 enable the 10 kΩ excitation resistor for CH0–CH3. Leave them open for voltage-output sensors. Close them only for bare resistive sensors (see [Connecting sensors](connecting-sensors.md)).

## Full-scale range

Set the range in software with `fsr=` when you create the `ADS1115` object (Raspberry Pi and MicroPython alike), or change `adc.fsr` between reads. Choose the smallest range that still covers your highest voltage.

| `fsr` | Full-scale range | Resolution (1 count) | Use for |
|---|---|---|---|
| 6.144 | ±6.144 V | 187.5 µV | Boards powered from 5 V, including RES-mode channels |
| 4.096 (default) | ±4.096 V | 125 µV | Boards powered from 3.3 V |
| 2.048 | ±2.048 V | 62.5 µV | Signals below 2 V |
| 1.024 | ±1.024 V | 31.3 µV | Signals below 1 V |
| 0.512 | ±0.512 V | 15.6 µV | Small signals, differential pairs |
| 0.256 | ±0.256 V | 7.8 µV | Very small differential signals |

No range lets an input exceed VDD: On a 3.3 V board, the ±6.144 V and ±4.096 V settings both read 0–3.3 V.

A reading that reaches the full-scale range is not valid, so the libraries raise `InputRangeError` with the range to use instead. On a 5 V board with `fsr=4.096`, a resistive sensor above 45 kΩ reaches it: A 10 kΩ thermistor colder than −5 °C. Use `fsr=6.144` on a 5 V board.

## Data rate

Set the rate with `rate=` or `adc.rate`: 8–860 samples/s. Slower rates give lower noise. 128 samples/s suits most sensors, and 8 samples/s suits calibration and slow sensors such as temperature.

## Differential inputs

Pairs CH0–CH1, CH0–CH3, CH1–CH3 and CH2–CH3 can be read differentially, for example across a current-sense resistor. Both inputs must stay between GND and VDD, and both channels' RES jumpers must be open.
