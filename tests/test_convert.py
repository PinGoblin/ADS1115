"""Unit tests for python/pingoblin_ads1115/convert.py (constants, conversion maths and
calibration files) and the package's public names."""
import json
import math
import os
import re
import tempfile
import unittest

import fakes

pkg, _ = fakes.load_pi_driver()


def beta_resistance(t_c, r0=10_000.0, t0_c=25.0, beta=3950.0):
    """Thermistor resistance at t_c from the Beta equation (the inverse of ntc_celsius)."""
    return r0 * math.exp(beta * (1 / (t_c + 273.15) - 1 / (t0_c + 273.15)))


class TestPackage(unittest.TestCase):
    def test_public_names(self):
        for name in pkg.__all__:
            with self.subTest(name=name):
                self.assertTrue(hasattr(pkg, name))

    def test_version_matches_pyproject(self):
        with open(os.path.join(fakes.PY_DIR, "pyproject.toml")) as f:
            self.assertEqual(re.search(r'^version = "([^"]+)"', f.read(), re.M).group(1), pkg.__version__)

    def test_constants(self):
        self.assertEqual((pkg.R_EXCITATION, pkg.R_SERIES, pkg.VDD_NOMINAL), (10_000.0, 4_700.0, 3.3))
        self.assertEqual(pkg.ADDRESSES, (0x48, 0x49, 0x4A, 0x4B))
        self.assertEqual(sorted(pkg.ADDRESS_JUMPERS.values()), list(pkg.ADDRESSES))
        self.assertEqual(pkg.ADDRESS_JUMPERS["JP1 (default)"], 0x48)
        self.assertEqual(pkg.CAL_FILE, "calibration.json")


class TestResistanceFromVoltage(unittest.TestCase):
    def test_half_supply_equals_excitation_resistor(self):
        self.assertAlmostEqual(pkg.resistance_from_voltage(1.65, 3.3), 10_000.0)

    def test_round_trip_over_sensor_range(self):
        for r in (10, 100, 1_000, 10_000, 100_000, 1_000_000):
            for vdd in (3.0, 3.3, 5.0):
                with self.subTest(r=r, vdd=vdd):
                    v = vdd * r / (r + 10_000)
                    self.assertAlmostEqual(pkg.resistance_from_voltage(v, vdd) / r, 1.0, places=9)

    def test_short_and_open(self):
        self.assertEqual(pkg.resistance_from_voltage(0.0, 3.3), 0.0)
        self.assertEqual(pkg.resistance_from_voltage(-0.01, 3.3), 0.0)
        self.assertEqual(pkg.resistance_from_voltage(3.3, 3.3), math.inf)
        self.assertEqual(pkg.resistance_from_voltage(3.4, 3.3), math.inf)

    def test_defaults_and_custom_resistor(self):
        self.assertAlmostEqual(pkg.resistance_from_voltage(pkg.VDD_NOMINAL / 2), pkg.R_EXCITATION)
        self.assertAlmostEqual(pkg.resistance_from_voltage(1.65, 3.3, r_excitation=4_700), 4_700)


class TestNtcCelsius(unittest.TestCase):
    def test_reference_point_and_round_trip(self):
        self.assertAlmostEqual(pkg.ntc_celsius(10_000), 25.0, places=9)
        for t in (-40, -10, 0, 37.5, 60, 100, 125):
            with self.subTest(t=t):
                self.assertAlmostEqual(pkg.ntc_celsius(beta_resistance(t)), t, places=6)

    def test_typical_b3950_values(self):
        self.assertAlmostEqual(pkg.ntc_celsius(32_650), 0.0, delta=1.0)
        self.assertAlmostEqual(pkg.ntc_celsius(3_588), 50.0, delta=1.0)

    def test_falls_as_resistance_rises(self):
        temps = [pkg.ntc_celsius(r) for r in (500, 1_000, 5_000, 10_000, 50_000, 100_000)]
        self.assertEqual(temps, sorted(temps, reverse=True))

    def test_custom_datasheet_values(self):
        self.assertAlmostEqual(pkg.ntc_celsius(47_000, r0=47_000, t0_c=20.0, beta=3435), 20.0)
        r = beta_resistance(60.0, r0=100_000, beta=4250)
        self.assertAlmostEqual(pkg.ntc_celsius(r, r0=100_000, beta=4250), 60.0, places=6)

    def test_short_and_open_give_nan(self):
        for r in (0, -1, math.inf):
            with self.subTest(r=r):
                self.assertTrue(math.isnan(pkg.ntc_celsius(r)))


class TestPercentOfRange(unittest.TestCase):
    def test_values(self):
        self.assertEqual(pkg.percent_of_range(1.65, 0.0, 3.3), 50.0)
        self.assertEqual(pkg.percent_of_range(-0.2, 0.0, 3.3), 0.0)
        self.assertEqual(pkg.percent_of_range(4.0, 0.0, 3.3), 100.0)
        self.assertAlmostEqual(pkg.percent_of_range(1.5, 1.0, 2.0), 50.0)
        self.assertAlmostEqual(pkg.percent_of_range(0.825, 3.3, 0.0), 75.0)   # inverted range
        self.assertEqual(pkg.percent_of_range(1.0, 2.0, 2.0), 0.0)
        self.assertAlmostEqual(pkg.percent_of_range(pkg.VDD_NOMINAL / 4), 25.0)


class TestCalibration(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.path = os.path.join(self.dir, "cal.json")

    def test_missing_or_corrupt_file_means_no_correction(self):
        self.assertEqual(pkg.load_calibration(self.path), {})
        with open(self.path, "w") as f:
            f.write("{not json")
        self.assertEqual(pkg.load_calibration(self.path), {})

    def test_round_trip_and_format(self):
        pkg.save_calibration({"3": 0.9985, "0": 1.001}, self.path)
        self.assertEqual(pkg.load_calibration(self.path), {"0": 1.001, "3": 0.9985})
        with open(self.path) as f:
            text = f.read()
        self.assertLess(text.index('"0"'), text.index('"3"'))
        self.assertEqual(json.loads(text), {"0": 1.001, "3": 0.9985})

    def test_default_file_is_in_working_directory(self):
        with fakes.working_directory(self.dir):
            pkg.save_calibration({"1": 1.01})
            self.assertEqual(pkg.load_calibration(), {"1": 1.01})
        self.assertTrue(os.path.exists(os.path.join(self.dir, "calibration.json")))

    def test_apply(self):
        cal = {"0": 1.01, "2": "0.99"}
        self.assertAlmostEqual(pkg.apply_calibration(2.0, 0, cal), 2.02)
        self.assertAlmostEqual(pkg.apply_calibration(2.0, 2, cal), 1.98)
        self.assertEqual(pkg.apply_calibration(1.234, 1, cal), 1.234)
        self.assertEqual(pkg.apply_calibration(1.234, 1, {}), 1.234)


if __name__ == "__main__":
    unittest.main()
