# Configuration

Three things can be configured: the I²C address and each channel's RES mode, set with solder jumpers, and the gain, set in software.

**Working with solder jumpers.** To close a jumper, heat both pads with a soldering iron and add a small blob of solder so it bridges them. To open JP1, cut the thin copper trace between its pads with a sharp craft knife, then check with a multimeter that the pads are no longer connected. Re-solder JP1 to restore the default.

**I²C address.** Exactly one address jumper must be closed.

| Address | JP1 (GND) | JP2 (VDD) | JP3 (SDA) | JP4 (SCL) |
|---|---|---|---|---|
| 0x48 (default) | Closed | Open | Open | Open |
| 0x49 | Cut | Closed | Open | Open |
| 0x4A | Cut | Open | Closed | Open |
| 0x4B | Cut | Open | Open | Closed |

**Using several boards.** Give each board a different address and daisy-chain them with Qwiic cables, or wire the J1 headers in parallel. Each board adds 10 kΩ pull-ups to the bus; up to four boards is fine for the bus. Example [`04_multiple_boards.py`](../api/examples-python.md#04_multiple_boardspy) finds and reads all of them. Qwiic cables carry only GND, VDD, SDA and SCL: to use the RDY signal, wire each board's J1 pin 5 to its own GPIO (the examples poll instead, so RDY is optional).

**RES jumpers.** JP5–JP8 enable the 10 kΩ excitation resistor for CH0–CH3. Leave them open for voltage-output sensors; close them only for bare resistive sensors (see [Connecting sensors](connecting-sensors.md)).

**Gain (programmable full-scale range).** Set in software with `ads.gain` (Adafruit library) or `fsr=` (MicroPython driver). Choose the smallest range that still covers your highest expected voltage.

| `ads.gain` | Full-scale range | Resolution (1 count) | Use for |
|---|---|---|---|
| 2/3 | ±6.144 V | 187.5 µV | Boards powered at 5 V |
| 1 (recommended) | ±4.096 V | 125 µV | Anything up to 3.3 V |
| 2 | ±2.048 V | 62.5 µV | Signals below 2 V |
| 4 | ±1.024 V | 31.3 µV | Signals below 1 V |
| 8 | ±0.512 V | 15.6 µV | Small signals, differential pairs |
| 16 | ±0.256 V | 7.8 µV | Very small differential signals |

The full-scale range never lets an input exceed VDD: on a 3.3 V board, the ±6.144 V and ±4.096 V settings both still read 0–3.3 V.

**Data rate.** Set with `ads.data_rate` (8 to 860 samples/s). Slower rates give lower noise; 128 samples/s is a good default, and 8 samples/s is best for calibration and slow sensors such as temperature.

**Differential inputs.** Pairs CH0–CH1, CH0–CH3, CH1–CH3 and CH2–CH3 can be read differentially, for example across a current-sense resistor. Both inputs must stay between GND and VDD, and both channels' RES jumpers must be open.
