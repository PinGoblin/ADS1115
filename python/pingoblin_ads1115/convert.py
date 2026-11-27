"""Board constants and conversion maths for the PinGoblin ADS1115 board.

Pure Python with no hardware access, so these functions run and can be tested on any
computer. They are the same on every host.

Example:
    ```python
    from pingoblin_ads1115 import ADS1115, resistance_from_voltage, ntc_celsius

    adc = ADS1115()
    v = adc.read_voltage(0, samples=16)                  # CH0 (J2), RES jumper JP5 closed
    print(ntc_celsius(resistance_from_voltage(v, vdd=3.30)))
    ```
"""
from __future__ import annotations

import json
import math

# --------------------------------------------------------------------------
# Board constants
# --------------------------------------------------------------------------
R_EXCITATION = 10_000.0
"""Excitation resistor R5–R8 (Ω), connected from VDD to SIG when a channel's RES jumper is closed."""

R_SERIES = 4_700.0
"""Series protection resistor R1–R4 (Ω) between each SIG pin and the ADC input. For reference only."""

VDD_NOMINAL = 3.3
"""Assumed supply voltage (V). Measure the real VDD at TP5–TP6 and set this for accurate resistive readings."""

ADDRESS_JUMPERS = {"JP1 (default)": 0x48, "JP2": 0x49, "JP3": 0x4A, "JP4": 0x4B}
"""I²C address selected by each address jumper. Exactly one jumper must be closed."""

CAL_FILE = "calibration.json"
"""Default calibration file, `calibration.json` in the current working directory. Written by `06_calibrate.py`."""


# --------------------------------------------------------------------------
# Conversion maths (pure functions, no hardware needed)
# --------------------------------------------------------------------------
def resistance_from_voltage(v_adc: float, vdd: float = VDD_NOMINAL, r_excitation: float = R_EXCITATION) -> float:
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


def ntc_celsius(r_ntc: float, r0: float = 10_000.0, t0_c: float = 25.0, beta: float = 3950.0) -> float:
    """Convert an NTC thermistor's resistance to temperature with the Beta equation.

    `1/T = 1/T0 + ln(R/R0) / B`, with T in kelvin.

    Args:
        r_ntc: Thermistor resistance (Ω), for example from
            [`resistance_from_voltage()`][pingoblin_ads1115.resistance_from_voltage].
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


def percent_of_range(v_adc: float, v_min: float = 0.0, v_max: float = VDD_NOMINAL) -> float:
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
def load_calibration(path: str | None = None) -> dict[str, float]:
    """Load per-channel gain factors.

    Args:
        path: Calibration file. `None` uses [`CAL_FILE`][pingoblin_ads1115.CAL_FILE].

    Returns:
        Dictionary of channel number (as a string) to gain factor, for example
        `{"0": 1.001}`. Empty if the file is missing or unreadable, which means no correction.
    """
    try:
        with open(path or CAL_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def apply_calibration(v_adc: float, ch: int, cal: dict[str, float]) -> float:
    """Correct a reading with the stored gain factor for its channel.

    Args:
        v_adc: Voltage measured on the channel (V).
        ch: Channel number, 0 to 3.
        cal: Factors from [`load_calibration()`][pingoblin_ads1115.load_calibration].

    Returns:
        Corrected voltage (V). Unchanged if the channel has no stored factor.
    """
    return v_adc * float(cal.get(str(ch), 1.0))


def save_calibration(cal: dict[str, float], path: str | None = None) -> None:
    """Save per-channel gain factors as JSON.

    Args:
        cal: Dictionary of channel number (as a string) to gain factor.
        path: Calibration file. `None` uses [`CAL_FILE`][pingoblin_ads1115.CAL_FILE].
    """
    with open(path or CAL_FILE, "w") as f:
        json.dump(cal, f, indent=2, sort_keys=True)
