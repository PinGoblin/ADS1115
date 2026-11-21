"""Unit tests for python/breakout_ads.py (the Raspberry Pi module)."""
import json
import math
import os
import sys
import tempfile
import unittest
from unittest import mock

import fakes

sys.path.insert(0, fakes.PY_DIR)
import breakout_ads as b  # noqa: E402


def beta_resistance(t_c, r0=10_000.0, t0_c=25.0, beta=3950.0):
    """Thermistor resistance at t_c from the Beta equation (the inverse of ntc_celsius)."""
    return r0 * math.exp(beta * (1 / (t_c + 273.15) - 1 / (t0_c + 273.15)))


class TestConstants(unittest.TestCase):
    def test_component_values(self):
        self.assertEqual(b.R_EXCITATION, 10_000.0)
        self.assertEqual(b.R_SERIES, 4_700.0)
        self.assertEqual(b.VDD_NOMINAL, 3.3)

    def test_addresses_cover_all_four_jumpers(self):
        self.assertEqual(sorted(b.ADDRESSES.values()), [0x48, 0x49, 0x4A, 0x4B])
        self.assertEqual(b.ADDRESSES["JP1 (default)"], 0x48)

    def test_gain_table_matches_datasheet(self):
        self.assertEqual(b.GAIN_FSR, {2 / 3: 6.144, 1: 4.096, 2: 2.048, 4: 1.024, 8: 0.512, 16: 0.256})
        for gain, fsr in b.GAIN_FSR.items():
            self.assertAlmostEqual(gain * fsr, 4.096, places=3)

    def test_cal_file_sits_next_to_module(self):
        self.assertEqual(os.path.dirname(b.CAL_FILE), os.path.dirname(os.path.abspath(b.__file__)))
        self.assertEqual(os.path.basename(b.CAL_FILE), "calibration.json")


class TestResistanceFromVoltage(unittest.TestCase):
    def test_half_supply_equals_excitation_resistor(self):
        self.assertAlmostEqual(b.resistance_from_voltage(1.65, 3.3), 10_000.0)

    def test_known_divider(self):
        self.assertAlmostEqual(b.resistance_from_voltage(1.0, 3.3), 10_000 * 1.0 / 2.3)

    def test_round_trip_over_sensor_range(self):
        for r in (10, 100, 1_000, 4_700, 10_000, 47_000, 100_000, 1_000_000):
            for vdd in (3.0, 3.3, 5.0):
                v = vdd * r / (r + 10_000)
                with self.subTest(r=r, vdd=vdd):
                    self.assertAlmostEqual(b.resistance_from_voltage(v, vdd) / r, 1.0, places=9)

    def test_short_circuit(self):
        self.assertEqual(b.resistance_from_voltage(0.0, 3.3), 0.0)
        self.assertEqual(b.resistance_from_voltage(-0.01, 3.3), 0.0)   # noise below zero

    def test_open_circuit(self):
        self.assertEqual(b.resistance_from_voltage(3.3, 3.3), math.inf)
        self.assertEqual(b.resistance_from_voltage(3.4, 3.3), math.inf)

    def test_defaults_use_board_constants(self):
        self.assertAlmostEqual(b.resistance_from_voltage(b.VDD_NOMINAL / 2), b.R_EXCITATION)

    def test_custom_excitation_resistor(self):
        self.assertAlmostEqual(b.resistance_from_voltage(1.65, 3.3, r_excitation=4_700), 4_700)


class TestNtcCelsius(unittest.TestCase):
    def test_reference_point(self):
        self.assertAlmostEqual(b.ntc_celsius(10_000), 25.0, places=9)

    def test_round_trip(self):
        for t in (-40, -10, 0, 25, 37.5, 60, 100, 125):
            with self.subTest(t=t):
                self.assertAlmostEqual(b.ntc_celsius(beta_resistance(t)), t, places=6)

    def test_typical_b3950_table_values(self):
        self.assertAlmostEqual(b.ntc_celsius(32_650), 0.0, delta=1.0)
        self.assertAlmostEqual(b.ntc_celsius(3_588), 50.0, delta=1.0)
        self.assertAlmostEqual(b.ntc_celsius(698), 100.0, delta=1.0)

    def test_falls_as_resistance_rises(self):
        temps = [b.ntc_celsius(r) for r in (500, 1_000, 5_000, 10_000, 50_000, 100_000)]
        self.assertEqual(temps, sorted(temps, reverse=True))

    def test_custom_datasheet_values(self):
        self.assertAlmostEqual(b.ntc_celsius(47_000, r0=47_000, t0_c=20.0, beta=3435), 20.0)
        t = 60.0
        r = beta_resistance(t, r0=100_000, beta=4250)
        self.assertAlmostEqual(b.ntc_celsius(r, r0=100_000, beta=4250), t, places=6)

    def test_short_and_open_give_nan(self):
        for r in (0, -1, math.inf):
            with self.subTest(r=r):
                self.assertTrue(math.isnan(b.ntc_celsius(r)))


class TestPercentOfRange(unittest.TestCase):
    def test_midpoint_and_ends(self):
        self.assertEqual(b.percent_of_range(1.65, 0.0, 3.3), 50.0)
        self.assertEqual(b.percent_of_range(0.0, 0.0, 3.3), 0.0)
        self.assertEqual(b.percent_of_range(3.3, 0.0, 3.3), 100.0)

    def test_clamped(self):
        self.assertEqual(b.percent_of_range(-0.2, 0.0, 3.3), 0.0)
        self.assertEqual(b.percent_of_range(4.0, 0.0, 3.3), 100.0)

    def test_offset_range(self):
        self.assertAlmostEqual(b.percent_of_range(1.5, 1.0, 2.0), 50.0)

    def test_inverted_range(self):
        self.assertAlmostEqual(b.percent_of_range(0.0, 3.3, 0.0), 100.0)
        self.assertAlmostEqual(b.percent_of_range(0.825, 3.3, 0.0), 75.0)

    def test_empty_range(self):
        self.assertEqual(b.percent_of_range(1.0, 2.0, 2.0), 0.0)

    def test_defaults(self):
        self.assertAlmostEqual(b.percent_of_range(b.VDD_NOMINAL / 4), 25.0)


class TestCalibration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "cal.json")

    def test_missing_file_means_no_correction(self):
        self.assertEqual(b.load_calibration(self.path), {})

    def test_corrupt_file_means_no_correction(self):
        with open(self.path, "w") as f:
            f.write("{not json")
        self.assertEqual(b.load_calibration(self.path), {})

    def test_save_and_load_round_trip(self):
        cal = {"0": 1.001, "3": 0.9985}
        b.save_calibration(cal, self.path)
        self.assertEqual(b.load_calibration(self.path), cal)

    def test_saved_file_is_readable_json(self):
        b.save_calibration({"3": 1.0, "0": 1.002}, self.path)
        with open(self.path) as f:
            text = f.read()
        self.assertEqual(json.loads(text), {"0": 1.002, "3": 1.0})
        self.assertLess(text.index('"0"'), text.index('"3"'))   # sorted keys
        self.assertIn("\n  ", text)                               # indented

    def test_default_path_is_cal_file(self):
        with mock.patch.object(b, "CAL_FILE", self.path):
            b.save_calibration({"1": 1.01})
            self.assertEqual(b.load_calibration(), {"1": 1.01})
        self.assertTrue(os.path.exists(self.path))

    def test_apply_uses_channel_factor(self):
        cal = {"0": 1.01, "2": 0.99}
        self.assertAlmostEqual(b.apply_calibration(2.0, 0, cal), 2.02)
        self.assertAlmostEqual(b.apply_calibration(2.0, 2, cal), 1.98)

    def test_apply_without_factor_is_unchanged(self):
        self.assertEqual(b.apply_calibration(1.234, 1, {"0": 1.01}), 1.234)
        self.assertEqual(b.apply_calibration(1.234, 1, {}), 1.234)

    def test_apply_accepts_factor_stored_as_text(self):
        self.assertAlmostEqual(b.apply_calibration(1.0, 0, {"0": "1.5"}), 1.5)


class _AdafruitTestCase(unittest.TestCase):
    layout = 3

    def setUp(self):
        self.fake = fakes.FakeAdafruit({0x48: [1.0, 1.65, 2.5, 3.0], 0x4B: [0.1, 0.2, 0.3, 0.4]},
                                       layout=self.layout)
        patcher = mock.patch.dict(sys.modules, self.fake.modules())
        patcher.start()
        self.addCleanup(patcher.stop)


class TestOpenAdcLibrary3(_AdafruitTestCase):
    layout = 3

    def test_defaults(self):
        ads = b.open_adc()
        self.assertEqual((ads.address, ads.gain, ads.data_rate), (0x48, 1, 128))
        self.assertIs(ads.i2c, self.fake.i2c)

    def test_settings_are_applied(self):
        ads = b.open_adc(address=0x4B, gain=2 / 3, data_rate=860)
        self.assertEqual((ads.address, ads.gain, ads.data_rate), (0x4B, 2 / 3, 860))

    def test_missing_board_raises_value_error(self):
        with self.assertRaises(ValueError):
            b.open_adc(address=0x49)

    def test_single_ended_channel(self):
        ads = b.open_adc()
        self.assertEqual([b.channel(ads, ch).voltage for ch in range(4)], [1.0, 1.65, 2.5, 3.0])

    def test_differential_channel(self):
        ads = b.open_adc()
        self.assertAlmostEqual(b.channel(ads, 0, 1).voltage, -0.65)
        self.assertAlmostEqual(b.channel(ads, 2, 3).voltage, -0.5)

    def test_channel_zero_negative_input_is_differential(self):
        ads = b.open_adc()
        self.assertAlmostEqual(b.channel(ads, 1, 0).voltage, 0.65)


class TestOpenAdcLibrary2(TestOpenAdcLibrary3):
    layout = 2


class TestMissingLibraries(unittest.TestCase):
    def test_no_adafruit_library(self):
        fake = fakes.FakeAdafruit({0x48: [0] * 4})
        mods = fake.modules()
        mods["adafruit_ads1x15"] = None          # makes the import fail
        with mock.patch.dict(sys.modules, mods), self.assertRaises(ImportError):
            b.open_adc()

    def test_no_blinka(self):
        with mock.patch.dict(sys.modules, {"board": None}), self.assertRaises(ImportError):
            b.open_adc()


class TestReadAverage(unittest.TestCase):
    class Chan:
        def __init__(self, values):
            self.values = list(values)
            self.reads = 0

        @property
        def voltage(self):
            self.reads += 1
            return self.values[(self.reads - 1) % len(self.values)]

    def test_mean_of_readings(self):
        chan = self.Chan([1.0, 2.0, 3.0, 4.0])
        self.assertAlmostEqual(b.read_average(chan, 4), 2.5)
        self.assertEqual(chan.reads, 4)

    def test_default_is_eight_readings(self):
        chan = self.Chan([1.0])
        self.assertEqual(b.read_average(chan), 1.0)
        self.assertEqual(chan.reads, 8)

    def test_single_reading(self):
        self.assertEqual(b.read_average(self.Chan([0.123]), 1), 0.123)

    def test_returns_float(self):
        self.assertIsInstance(b.read_average(self.Chan([1]), 2), float)


if __name__ == "__main__":
    unittest.main()
