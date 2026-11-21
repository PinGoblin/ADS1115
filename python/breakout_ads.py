"""Helper module for the PinGoblin ADS1115 4-channel ADC breakout on a Raspberry Pi.

Every example script imports this module, so keep it in the same folder as them. It:

- hides the differences between versions 2.x and 3.x of the Adafruit
  [`adafruit-circuitpython-ads1x15`](https://pypi.org/project/adafruit-circuitpython-ads1x15/)
  library,
- holds the board's component values, and
- provides the conversion maths for resistive sensors, thermistors and calibration.

The conversion functions are pure Python and need no hardware, so they can be used and
tested on any computer.

Install the library on the Pi in a virtual environment:

```bash
python3 -m venv ~/ads-env && source ~/ads-env/bin/activate
pip install adafruit-circuitpython-ads1x15
```

Example:
    ```python
    from breakout_ads import open_adc, channel, read_average

    ads = open_adc()                 # address 0x48, gain 1 (±4.096 V), 128 samples/s
    ch0 = channel(ads, 0)
    print(read_average(ch0, 16))     # volts
    ```
"""
import json
import math
import os

# --------------------------------------------------------------------------
# Board constants
# --------------------------------------------------------------------------
R_EXCITATION = 10_000.0
"""Excitation resistor R5–R8 (Ω), connected from VDD to SIG when a channel's RES jumper is closed."""

R_SERIES = 4_700.0
"""Series protection resistor R1–R4 (Ω) between each SIG pin and the ADC input. For reference only."""

VDD_NOMINAL = 3.3
"""Assumed supply voltage (V). Measure the real VDD at TP5–TP6 and set this for accurate resistive readings."""

ADDRESSES = {"JP1 (default)": 0x48, "JP2": 0x49, "JP3": 0x4A, "JP4": 0x4B}
"""I²C address selected by each address jumper. Exactly one jumper must be closed."""

GAIN_FSR = {2 / 3: 6.144, 1: 4.096, 2: 2.048, 4: 1.024, 8: 0.512, 16: 0.256}
"""Adafruit `gain` setting to full-scale range (±V). Gain 1 (±4.096 V) suits a 3.3 V board."""

CAL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calibration.json")
"""Default calibration file, `calibration.json` next to this module. Written by `06_calibrate.py`."""


# --------------------------------------------------------------------------
# Library access (works with old and new adafruit-circuitpython-ads1x15)
# --------------------------------------------------------------------------
def open_adc(address=0x48, gain=1, data_rate=128):
    """Open the board on the Raspberry Pi's default I²C bus.

    Works with versions 2.x and 3.x of the Adafruit ADS1x15 library.

    Args:
        address: I²C address set by the address jumpers: `0x48` (default), `0x49`, `0x4A` or `0x4B`.
        gain: Programmable gain, one of the keys of [`GAIN_FSR`][breakout_ads.GAIN_FSR].
            Use the smallest range that still covers your highest input voltage.
        data_rate: Samples per second: 8, 16, 32, 64, 128, 250, 475 or 860.
            Slower rates give lower noise.

    Returns:
        A configured Adafruit `ADS1115` object.

    Raises:
        ValueError: If no device answers at `address`.
        ImportError: If Blinka or the Adafruit library is not installed.
    """
    import board  # Blinka; only needed on real hardware
    try:  # library 3.x and later
        from adafruit_ads1x15 import ADS1115
    except ImportError:  # library 2.x
        from adafruit_ads1x15.ads1115 import ADS1115
    ads = ADS1115(board.I2C(), address=address)
    ads.gain = gain
    ads.data_rate = data_rate
    return ads


def channel(ads, ch, ch_neg=None):
    """Return an input channel, single-ended or differential.

    Args:
        ads: Object returned by [`open_adc()`][breakout_ads.open_adc].
        ch: Channel number, 0 to 3 (CH0 is header J2, CH3 is J5).
        ch_neg: Negative input for a differential reading, or `None` for single-ended.
            Valid pairs are (0, 1), (0, 3), (1, 3) and (2, 3).

    Returns:
        An Adafruit `AnalogIn` object. Read `.voltage` (V) or `.value` (counts) from it.
    """
    try:
        from adafruit_ads1x15 import AnalogIn
    except ImportError:
        from adafruit_ads1x15.analog_in import AnalogIn
    if ch_neg is None:
        return AnalogIn(ads, ch)
    return AnalogIn(ads, ch, ch_neg)


def read_average(chan, samples=8):
    """Average several readings to reduce noise.

    Args:
        chan: Channel from [`channel()`][breakout_ads.channel].
        samples: Number of readings to average.

    Returns:
        Mean voltage (V).
    """
    total = 0.0
    for _ in range(samples):
        total += chan.voltage
    return total / samples


# --------------------------------------------------------------------------
# Conversion maths (pure functions, no hardware needed)
# --------------------------------------------------------------------------
def resistance_from_voltage(v_adc, vdd=VDD_NOMINAL, r_excitation=R_EXCITATION):
    """Work out a bare resistive sensor's resistance on a channel with its RES jumper closed.

    The 10 kΩ excitation resistor and the sensor form a voltage divider:

    `v_adc = vdd × Rs / (Rs + 10 kΩ)`, so `Rs = 10 kΩ × v_adc / (vdd − v_adc)`

    Args:
        v_adc: Voltage measured on the channel (V).
        vdd: Board supply voltage (V). Use the measured value for best accuracy.
        r_excitation: Excitation resistor (Ω).

    Returns:
        Sensor resistance (Ω): `0.0` for a short circuit and `math.inf` for an open circuit.
    """
    if v_adc <= 0.0:
        return 0.0
    if v_adc >= vdd:
        return math.inf
    return r_excitation * v_adc / (vdd - v_adc)


def ntc_celsius(r_ntc, r0=10_000.0, t0_c=25.0, beta=3950.0):
    """Convert an NTC thermistor's resistance to temperature with the Beta equation.

    `1/T = 1/T0 + ln(R/R0) / B`, with T in kelvin.

    Args:
        r_ntc: Thermistor resistance (Ω), for example from
            [`resistance_from_voltage()`][breakout_ads.resistance_from_voltage].
        r0: Resistance at `t0_c` (Ω), from the datasheet.
        t0_c: Reference temperature (°C), usually 25.
        beta: Beta value (K), from the datasheet. 3950 is common.

    Returns:
        Temperature (°C), or `nan` for a short or open circuit.
    """
    if r_ntc <= 0 or math.isinf(r_ntc):
        return float("nan")
    t0_k = t0_c + 273.15
    inv_t = 1.0 / t0_k + math.log(r_ntc / r0) / beta
    return 1.0 / inv_t - 273.15


def percent_of_range(v_adc, v_min=0.0, v_max=VDD_NOMINAL):
    """Map a voltage onto 0 to 100 %, for potentiometers, soil probes or LDRs.

    Args:
        v_adc: Voltage measured on the channel (V).
        v_min: Voltage that maps to 0 % (V).
        v_max: Voltage that maps to 100 % (V).

    Returns:
        Percentage, clamped to 0–100. Returns `0.0` if `v_min` equals `v_max`.
    """
    if v_max == v_min:
        return 0.0
    pct = 100.0 * (v_adc - v_min) / (v_max - v_min)
    return max(0.0, min(100.0, pct))


# --------------------------------------------------------------------------
# Calibration (written by 06_calibrate.py)
# --------------------------------------------------------------------------
def load_calibration(path=None):
    """Load per-channel gain factors.

    Args:
        path: Calibration file. `None` uses [`CAL_FILE`][breakout_ads.CAL_FILE].

    Returns:
        Dictionary of channel number (as a string) to gain factor, for example
        `{"0": 1.001}`. Empty if the file is missing or unreadable, which means no correction.
    """
    try:
        with open(path or CAL_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def apply_calibration(v_adc, ch, cal):
    """Correct a reading with the stored gain factor for its channel.

    Args:
        v_adc: Voltage measured on the channel (V).
        ch: Channel number, 0 to 3.
        cal: Factors from [`load_calibration()`][breakout_ads.load_calibration].

    Returns:
        Corrected voltage (V). Unchanged if the channel has no stored factor.
    """
    return v_adc * float(cal.get(str(ch), 1.0))


def save_calibration(cal, path=None):
    """Save per-channel gain factors as JSON.

    Args:
        cal: Dictionary of channel number (as a string) to gain factor.
        path: Calibration file. `None` uses [`CAL_FILE`][breakout_ads.CAL_FILE].
    """
    with open(path or CAL_FILE, "w") as f:
        json.dump(cal, f, indent=2, sort_keys=True)
