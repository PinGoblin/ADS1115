# Configuration

Three things can be configured: the I²C address and each channel's RES mode, set with solder jumpers, and the full-scale range and data rate, set in software.

**Working with solder jumpers.** To close a jumper, heat both pads with a soldering iron and add a small blob of solder so it bridges them. To open JP1, cut the thin copper trace between its pads with a sharp craft knife, then check with a multimeter that the pads are no longer connected. Re-solder JP1 to restore the default.

**I²C address.** Exactly one address jumper must be closed. If you close JP2 and forget to cut JP1, nothing is damaged (JP1 connects through a 10 kΩ resistor) and the board answers at 0x49, but JP1 must be cut for 0x4A and 0x4B or the bus stops working.

| Address | JP1 (GND) | JP2 (VDD) | JP3 (SDA) | JP4 (SCL) |
|---|---|---|---|---|
| 0x48 (default) | Closed | Open | Open | Open |
| 0x49 | Cut | Closed | Open | Open |
| 0x4A | Cut | Open | Closed | Open |
| 0x4B | Cut | Open | Open | Closed |

When you set up several boards, use the addresses in the order 0x48, 0x49, 0x4B and then 0x4A. Address 0x4A connects ADDR to SDA, which relies on the host holding SDA steady for 100 ns after each clock edge; TI recommends using it last.

**Using several boards.** Give each board a different address and wire their J1 pins 1–4 (VDD, GND, SCL, SDA) in parallel. Example [`04_multiple_boards.py`](../api/examples-python.md#04_multiple_boardspy) finds and reads all of them. To use the RDY signal, wire each board's J1 pin 5 to its own GPIO (the examples poll instead, so RDY is optional).

**Bus pull-ups and speed.** Each board adds 10 kΩ pull-ups on SDA and SCL. With a Raspberry Pi (1.8 kΩ on board), the bus can take four 10 kΩ pull-up pairs in total: four of these boards, or fewer boards plus other devices that have their own 10 kΩ pull-ups. More than that overloads the bus, which must be able to pull it low with 3 mA. With only the board's own pull-ups, as on an ESP32, run the bus at 100 kHz (the MicroPython examples do). For 400 kHz, add 2.2–4.7 kΩ resistors from SDA and SCL to 3.3 V at the host.

**RES jumpers.** JP5–JP8 enable the 10 kΩ excitation resistor for CH0–CH3. Leave them open for voltage-output sensors; close them only for bare resistive sensors (see [Connecting sensors](connecting-sensors.md)).

**Full-scale range (programmable gain).** Set in software with `fsr=` when you create the `ADS1115` object (Raspberry Pi and MicroPython alike), or change `adc.fsr` between reads. Choose the smallest range that still covers your highest expected voltage.

| `fsr` | Full-scale range | Resolution (1 count) | Use for |
|---|---|---|---|
| 6.144 | ±6.144 V | 187.5 µV | Boards powered at 5 V, including RES-mode channels |
| 4.096 (recommended) | ±4.096 V | 125 µV | Anything up to 3.3 V |
| 2.048 | ±2.048 V | 62.5 µV | Signals below 2 V |
| 1.024 | ±1.024 V | 31.3 µV | Signals below 1 V |
| 0.512 | ±0.512 V | 15.6 µV | Small signals, differential pairs |
| 0.256 | ±0.256 V | 7.8 µV | Very small differential signals |

The full-scale range never lets an input exceed VDD: on a 3.3 V board, the ±6.144 V and ±4.096 V settings both still read 0–3.3 V.

A reading above the full-scale range stops at full scale. After each read, `adc.clipped` is `True` if any conversion hit full scale. On a 5 V board with `fsr=4.096`, a resistive sensor above about 45 kΩ (a 10 kΩ thermistor colder than about −5 °C) clips, so use `fsr=6.144` there.

**Data rate.** Set with `rate=` or `adc.rate` (8 to 860 samples/s). Slower rates give lower noise; 128 samples/s is a good default, and 8 samples/s is best for calibration and slow sensors such as temperature.

**Differential inputs.** Pairs CH0–CH1, CH0–CH3, CH1–CH3 and CH2–CH3 can be read differentially, for example across a current-sense resistor. Both inputs must stay between GND and VDD, and both channels' RES jumpers must be open.
