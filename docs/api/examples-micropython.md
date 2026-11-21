# MicroPython examples

The scripts in the [`micropython/`](https://github.com/PinGoblin/ADS1115/tree/main/micropython) folder. Copy [`ads1115.py`](reference/ads1115.md) to the board first. Copy `main.py` to run it at boot, or run a script once with `mpremote run <script>`.

| Script | What it does | Jumper setting |
|---|---|---|
| [`main.py`](#mainpy) | Thermistor on CH0 plus voltages on CH1–CH3 | CH0 RES closed, CH1–CH3 RES open |
| [`ready_pin_fast.py`](#ready_pin_fastpy) | Samples at 860 per second using the RDY pin (J1 pin 5 to GPIO4) as an interrupt | Any |

## main.py

```python title="micropython/main.py"
--8<-- "micropython/main.py"
```

## ready_pin_fast.py

```python title="micropython/ready_pin_fast.py"
--8<-- "micropython/ready_pin_fast.py"
```
