"""
Helper module for the 4-channel ADS1115 ADC breakout (Rev F).

Keep this file in the same folder as the example scripts. It hides the
differences between versions of the Adafruit ADS1x15 library and holds
the board constants and conversion maths used by every example.

Install the library on a Raspberry Pi (in a virtual environment):
    python3 -m venv ~/ads-env && source ~/ads-env/bin/activate
    pip install adafruit-circuitpython-ads1x15
"""
import json
import math
import os

# --------------------------------------------------------------------------
# Board constants (Rev F)
# --------------------------------------------------------------------------
R_EXCITATION = 10_000.0   # R5-R8: VDD -> input when the RES jumper is closed
R_SERIES = 4_700.0        # R1-R4: series protection resistor (for reference)
VDD_NOMINAL = 3.3         # measure your actual VDD with a multimeter!

ADDRESSES = {"JP1 (default)": 0x48, "JP2": 0x49, "JP3": 0x4A, "JP4": 0x4B}

# Gain setting -> full-scale range (volts). Gain 1 (+/-4.096 V) suits a 3.3 V board.
GAIN_FSR = {2 / 3: 6.144, 1: 4.096, 2: 2.048, 4: 1.024, 8: 0.512, 16: 0.256}

CAL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calibration.json")


# --------------------------------------------------------------------------
# Library access (works with old and new adafruit-circuitpython-ads1x15)
# --------------------------------------------------------------------------
def open_adc(address=0x48, gain=1, data_rate=128):
    """Return a configured ADS1115 object on the default I2C bus."""
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
    """Return an AnalogIn for channel 0-3 (or a differential pair)."""
    try:
        from adafruit_ads1x15 import AnalogIn
    except ImportError:
        from adafruit_ads1x15.analog_in import AnalogIn
    if ch_neg is None:
        return AnalogIn(ads, ch)
    return AnalogIn(ads, ch, ch_neg)


def read_average(chan, samples=8):
    """Average several readings to reduce noise. Returns volts."""
    total = 0.0
    for _ in range(samples):
        total += chan.voltage
    return total / samples


# --------------------------------------------------------------------------
# Conversion maths (pure functions, no hardware needed)
# --------------------------------------------------------------------------
def resistance_from_voltage(v_adc, vdd=VDD_NOMINAL, r_excitation=R_EXCITATION):
    """Sensor resistance for a channel with its RES jumper closed.

    The 10 k excitation resistor and the sensor form a divider:
        v_adc = vdd * Rs / (Rs + 10k)  ->  Rs = 10k * v_adc / (vdd - v_adc)
    Returns math.inf for an open circuit and 0.0 for a short.
    """
    if v_adc <= 0.0:
        return 0.0
    if v_adc >= vdd:
        return math.inf
    return r_excitation * v_adc / (vdd - v_adc)


def ntc_celsius(r_ntc, r0=10_000.0, t0_c=25.0, beta=3950.0):
    """Temperature from an NTC thermistor using the Beta equation.

    1/T = 1/T0 + ln(R/R0)/B   (T in kelvin)
    r0, t0_c and beta come from the thermistor's datasheet (10k, 25 C, 3950 is common).
    """
    if r_ntc <= 0 or math.isinf(r_ntc):
        return float("nan")
    t0_k = t0_c + 273.15
    inv_t = 1.0 / t0_k + math.log(r_ntc / r0) / beta
    return 1.0 / inv_t - 273.15


def percent_of_range(v_adc, v_min=0.0, v_max=VDD_NOMINAL):
    """Map a voltage onto 0-100 % (handy for pots, soil probes, LDRs)."""
    if v_max == v_min:
        return 0.0
    pct = 100.0 * (v_adc - v_min) / (v_max - v_min)
    return max(0.0, min(100.0, pct))


# --------------------------------------------------------------------------
# Calibration (written by 06_calibrate.py)
# --------------------------------------------------------------------------
def load_calibration(path=None):
    """Return {"0": factor, ...}. Missing file -> no correction (factor 1.0)."""
    try:
        with open(path or CAL_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def apply_calibration(v_adc, ch, cal):
    """Multiply a reading by the stored gain factor for that channel."""
    return v_adc * float(cal.get(str(ch), 1.0))


def save_calibration(cal, path=None):
    with open(path or CAL_FILE, "w") as f:
        json.dump(cal, f, indent=2, sort_keys=True)
