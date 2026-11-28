# Quick start

Power the PinGoblin ADS1115 from the host's 3.3 V pin, connect four wires, install the library and run the first example. The board answers at I²C address 0x48 out of the box.

!!! danger "Use the host's 3.3 V pin, never 5 V"
    5 V on J1 puts 5 V on the host's I²C pins and can damage a Raspberry Pi or ESP32.

## Raspberry Pi wiring

| PinGoblin ADS1115 J1 | Raspberry Pi header |
|---|---|
| 1 VDD **(Required)** | Pin 1 (3V3) |
| 2 GND **(Required)** | Pin 6 (GND) |
| 3 SCL **(Required)** | Pin 5 (GPIO3 / SCL) |
| 4 SDA **(Required)** | Pin 3 (GPIO2 / SDA) |
| 5 RDY (Optional) | Any free GPIO |

## ESP32 DevKit wiring

| PinGoblin ADS1115 J1 | ESP32 DevKit |
|---|---|
| 1 VDD **(Required)** | 3V3 |
| 2 GND **(Required)** | GND |
| 3 SCL **(Required)** | GPIO22 |
| 4 SDA **(Required)** | GPIO21 |
| 5 RDY (Optional) | GPIO4 (used by `ready_pin_fast.py`) |

## Raspberry Pi software

1. Enable I²C: `sudo raspi-config` → Interface Options → I2C → Enable, then reboot.
2. Check the board is seen: `i2cdetect -y 1` shows `48`.
3. Install the library in a virtual environment:
    1. `python3 -m venv ~/ads-env`
    2. `source ~/ads-env/bin/activate`
    3. `pip install "git+https://github.com/PinGoblin/ADS1115#subdirectory=python"`
4. Copy the [`python`](https://github.com/PinGoblin/ADS1115/tree/main/python) folder from the repository to the Pi and run `python3 01_read_all_channels.py` inside it.

## ESP32 software (MicroPython)

1. Flash MicroPython onto the ESP32.
2. Copy `ads1115.py` and `main.py` from the [`micropython`](https://github.com/PinGoblin/ADS1115/tree/main/micropython) folder to the board with Thonny or `mpremote cp`.
3. Reset the ESP32. Readings print once a second.

With nothing connected to a channel, its input floats and shows random values. Connect a sensor to get a steady reading.
