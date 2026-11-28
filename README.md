# PinGoblin ADS1115 – 4-channel 16-bit ADC board

The PinGoblin ADS1115 adds four 16-bit analogue inputs to a Raspberry Pi, ESP32 or any other I²C host. It uses the TI ADS1115, and has a 3-pin sensor header (GND, VDD, SIG) per channel, protected inputs, solder-jumper configuration for resistive sensors and a 5 µA idle current.

**Documentation:** https://pingoblin.github.io/ADS1115/ (user guide and API reference)

## Contents

| Folder | What it is |
|---|---|
| [`python/`](python/) | Raspberry Pi: The `pingoblin_ads1115` package (built on `smbus2`) and six example scripts |
| [`micropython/`](micropython/) | ESP32 / MicroPython: `ads1115.py` module with no dependencies, plus two examples |
| [`docs/`](docs/) | MkDocs source for the documentation site |
| [`tests/`](tests/) | Unit tests for both libraries, every example and the docs, on simulated hardware |

## Quick start (Raspberry Pi)

```bash
sudo raspi-config        # Interface Options -> I2C -> Enable, then reboot
i2cdetect -y 1           # the board should appear at 48 (or 49/4a/4b)
python3 -m venv ~/ads-env && source ~/ads-env/bin/activate
pip install "git+https://github.com/PinGoblin/ADS1115#subdirectory=python"
cd python && python3 01_read_all_channels.py
```

## Quick start (ESP32, MicroPython)

Copy `micropython/ads1115.py` and `micropython/main.py` to the board (Thonny, or `mpremote cp ads1115.py main.py :`) and reset it. Default pins: SCL = GPIO22, SDA = GPIO21.

## Wiring

J1 pin 1 GND → GND, pin 2 VDD → 3V3, pin 3 SCL → SCL, pin 4 SDA → SDA. Power the board from **3.3 V** when it is wired to a Raspberry Pi or ESP32: Their I²C pins are not 5 V tolerant.

| RES jumper (per channel) | Sensor type |
|---|---|
| Open (default) | Voltage-output sensors and modules (0 V to VDD): Analogue modules, potentiometers, TMP36 |
| Closed | Bare resistive sensors between SIG and GND: 10 kΩ NTC thermistor, LDR, FSR, flex sensor |

I²C address 0x48 by default (JP1). Move the address jumper to JP2, JP3 or JP4 for 0x49, 0x4A or 0x4B, so up to four boards share one bus (use 0x4A last).

## Documentation

The documentation in `docs/` is the source of truth for the board and its code. CI builds it on every push and publishes it to GitHub Pages from `main`. To preview it locally:

```bash
pip install -r requirements-docs.txt
mkdocs serve
```

Docstrings use the Google style with Markdown, and are rendered into the API reference by mkdocstrings.

## Tests

The tests use only the Python standard library and simulated hardware: A register-level ADS1115 model, a fake `smbus2`, and fake MicroPython `machine` and `time` modules. They cover both libraries, every example (with and without `--mock`), and checks that the docs match the code and the documentation style rules. CI runs them on Python 3.11, 3.12 and 3.13.

```bash
python3 -m unittest discover -s tests
```

## Licence

MIT. See [LICENSE](LICENSE).
