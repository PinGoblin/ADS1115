# Connecting sensors

Most sensors plug straight into a channel header with the factory settings. Only bare resistive sensors need the channel's RES jumper closed.

| Sensor type | Examples | RES jumper | Header pins used | Reading |
|---|---|---|---|---|
| Voltage-output module (3 wires) | Analogue sensor modules, TMP36, capacitive soil probes, joysticks, Hall sensors | Open (default) | GND, VDD, SIG | Vin = Vadc |
| Potentiometer | Knobs, sliders | Open (default) | Ends to GND and VDD, wiper to SIG | % = Vadc / VDD × 100 |
| Bare resistive sensor (2 wires) | 10 kΩ NTC thermistor, LDR, force-sensitive resistor, flex sensor | Closed | SIG and GND only | Rs = 10 kΩ × Vadc / (VDD − Vadc) |
| 5 V sensor | MQ gas modules, 0.5–4.5 V pressure transducers | Open (default) | GND and SIG only; power the sensor from 5 V separately | See below |

**Voltage-output sensors.** Plug the sensor's 3-pin cable into the channel header, matching the GND, VDD and SIG labels on the silkscreen to the sensor's ground, supply and signal wires. Check that the sensor works at 3.3 V. Most maker modules accept 3.3–5 V.

**Resistive sensors.** Close the channel's RES jumper (JP5 for CH0, JP6 for CH1, JP7 for CH2, JP8 for CH3) with a small blob of solder. Connect one sensor lead to SIG and the other to GND. There is no polarity. The on-board 10 kΩ resistor and the sensor form a voltage divider. Sensors between 1 kΩ and 100 kΩ over your measuring range give the best resolution, and a 10 kΩ sensor gives the most resolution near its nominal value.

**5 V sensors.** Power the sensor from a separate 5 V supply, such as the Raspberry Pi's 5 V pin. Connect its ground to the header's GND pin and its output to SIG. The sensor's output must stay below VDD + 0.3 V: 3.6 V on a 3.3 V board. If it can go higher, add a resistor divider on the sensor side. The 4.7 kΩ series resistor protects the ADC from brief mistakes but is not a level shifter.

!!! danger "Never connect a 5 V sensor's supply to the header's VDD pin"
    The header's VDD is the board's supply. A 5 V supply on it reaches J1 and the host's 3.3 V rail.

**Cable runs.** Leads up to 3 m (final figure after prototype testing) need no special cable. For longer runs, use twisted or shielded cable and keep it away from mains and motor wiring. The 100 nF filter on each channel removes most interference.

**Not supported on this board.** Industrial 0–10 V and 4–20 mA signals, thermocouples, RTDs (PT100/PT1000), load cells and digital sensors (DHT22, DS18B20, I²C sensors). Thermocouples, RTDs and load cells need dedicated amplifier boards. Digital sensors connect to the host directly.
