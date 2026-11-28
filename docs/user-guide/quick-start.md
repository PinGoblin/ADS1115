# Quick start

Power the board from 3.3 V, connect four wires, install the library and run the first example. The board appears at I²C address 0x48 out of the box.

## Raspberry Pi wiring (J1)

| Breakout J1 | Raspberry Pi header |
|---|---|
| 1 VDD | Pin 1 (3V3) |
| 2 GND | Pin 6 (GND) |
| 3 SCL | Pin 5 (GPIO3 / SCL) |
| 4 SDA | Pin 3 (GPIO2 / SDA) |
| 5 RDY | Optional: any free GPIO |

## ESP32 DevKit wiring (J1)

VDD to 3V3, GND to GND, SCL to GPIO22, SDA to GPIO21.

## Raspberry Pi software

1. Enable I²C: `sudo raspi-config` → Interface Options → I2C → Enable, then reboot.
2. Check the board is seen: `i2cdetect -y 1` should show `48`.
3. Install the library in a virtual environment:
    1. `python3 -m venv ~/ads-env`
    2. `source ~/ads-env/bin/activate`
    3. `pip install "git+https://github.com/PinGoblin/ADS1115#subdirectory=python"`
4. Copy the [`python`](https://github.com/PinGoblin/ADS1115/tree/main/python) folder from the repository to the Pi and run `python3 01_read_all_channels.py` inside it.

## ESP32 software (MicroPython)

1. Flash MicroPython onto the ESP32.
2. Copy `ads1115.py` and `main.py` from the [`micropython`](https://github.com/PinGoblin/ADS1115/tree/main/micropython) folder to the board with Thonny or `mpremote cp`.
3. Reset the board; readings print once a second.

!!! note
    With nothing connected, the inputs float and show random values; this is normal.
