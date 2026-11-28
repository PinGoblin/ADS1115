"""Tests for the Raspberry Pi example scripts in python/, on a fake smbus2 bus."""
import csv
import json
import math
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

import fakes

pkg, drv = fakes.load_pi_driver()
VOLTS = [1.0, 1.65, 2.5, 3.0]


class _ExampleTestCase(unittest.TestCase):
    """Runs an example with simulated boards; `time.sleep` stops its loop after `loops` passes."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.cal_path = os.path.join(self.dir, "calibration.json")
        self.chip = fakes.ADS1115Chip(VOLTS)
        self.chips = {0x48: self.chip}
        self.smbus2 = fakes.make_smbus2(self.chips)
        patcher = mock.patch.object(drv, "time", fakes.FakeSleep())   # driver waits are instant
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_example(self, name, argv=(), loops=2, edits=None):
        side_effect = [None] * (loops - 1) + [KeyboardInterrupt]
        with mock.patch("time.sleep", side_effect=side_effect) as sleep:
            result = fakes.run_script(os.path.join(fakes.PY_DIR, name), argv,
                                      {"smbus2": self.smbus2}, cwd=self.dir, edits=edits)
        self.sleep = sleep
        return result

    def write_cal(self, cal):
        with open(self.cal_path, "w") as f:
            json.dump(cal, f)

    def configs(self, chip=None):
        return (chip or self.chip).config_writes()


class TestReadAllChannels(_ExampleTestCase):
    def test_prints_counts_and_volts(self):
        _, out, exc = self.run_example("01_read_all_channels.py")
        self.assertIsNone(exc)                       # Ctrl+C exits cleanly
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("CH0 (J2)"))
        self.assertEqual(len(lines), 3)
        self.assertEqual(re.findall(r"(\d+)\s+(\d\.\d{3})V", lines[1]),
                         [("8000", "1.000"), ("13200", "1.650"), ("20000", "2.500"), ("24000", "3.000")])
        self.sleep.assert_called_with(0.5)

    def test_applies_calibration(self):
        self.write_cal({"0": 1.01})
        _, out, _ = self.run_example("01_read_all_channels.py")
        self.assertIn("1.010V", out.splitlines()[1])

    def test_over_range_cell(self):
        self.chip.volts[2] = 5.0
        _, out, _ = self.run_example("01_read_all_channels.py", loops=1)
        self.assertIn(" 32767 over range", out.splitlines()[1])
        self.assertIn("3.000V", out.splitlines()[1])

    def test_uses_bus_1_and_closes_nothing_else(self):
        self.run_example("01_read_all_channels.py", loops=1)
        self.assertEqual([b.bus for b in self.smbus2.opened], [1])


class TestThermistor(_ExampleTestCase):
    def test_temperature_line(self):
        self.chip.volts[0] = 1.65                    # 10 kΩ = 25 °C
        _, out, exc = self.run_example("02_thermistor_ntc.py")
        self.assertIsNone(exc)
        self.assertIn("R= 10.000 k", out)
        self.assertIn("T= 25.00 C", out)

    def test_sixteen_samples(self):
        self.run_example("02_thermistor_ntc.py", loops=1)
        self.assertEqual(self.chip.conversions, 16)

    def test_open_circuit_even_just_below_vdd(self):
        for v in (3.3, 3.2995, 3.31):
            self.chip.volts[0] = v
            with self.subTest(v=v):
                _, out, _ = self.run_example("02_thermistor_ntc.py")
                self.assertIn("Open circuit: Check the thermistor is connected", out)
                self.assertNotIn("T=", out)

    def test_cold_thermistor_is_not_open(self):
        r = 10_000 * math.exp(3950 * (1 / 233.15 - 1 / 298.15))     # −40 °C, about 278 kΩ
        self.chip.volts[0] = 3.3 * r / (r + 10_000)
        _, out, _ = self.run_example("02_thermistor_ntc.py")
        self.assertIn("T=-40.00 C", out)

    def test_short_circuit(self):
        self.chip.volts[0] = 0.0
        _, out, _ = self.run_example("02_thermistor_ntc.py")
        self.assertIn("Short circuit: Check the thermistor wiring", out)

    def test_full_scale_warning_on_5v_board(self):
        self.chip.volts[0] = 4.5                     # cold NTC on a 5 V board, above ±4.096 V
        _, out, exc = self.run_example("02_thermistor_ntc.py", edits={"VDD = 3.30": "VDD = 5.00"})
        self.assertIsNone(exc)                       # keeps running and says what to change
        self.assertIn("CH0 is at the ±4.096 V full-scale limit", out)
        self.assertIn("ADS1115(fsr=6.144) on a board powered from 5 V", out)
        self.assertNotIn("T=", out)

    def test_no_warning_with_larger_range(self):
        self.chip.volts[0] = 4.5
        _, out, _ = self.run_example("02_thermistor_ntc.py", edits={
            "VDD = 3.30": "VDD = 5.00", "adc = ADS1115(bus, fsr=4.096)": "adc = ADS1115(bus, fsr=6.144)"})
        self.assertNotIn("full-scale", out)
        self.assertIn("T=", out)

    def test_live_vdd(self):
        self.chip.volts[0], self.chip.volts[3] = 1.6, 3.2
        _, out, _ = self.run_example("02_thermistor_ntc.py", edits={"VDD_CHANNEL = None": "VDD_CHANNEL = 3"})
        self.assertIn("VDD=3.200 V", out)
        self.assertIn("T= 25.00 C", out)

    def test_applies_calibration(self):
        self.chip.volts[0] = 1.5
        self.write_cal({"0": 1.1})
        _, out, _ = self.run_example("02_thermistor_ntc.py")
        self.assertIn("T= 25.00 C", out)


class TestLightAndPot(_ExampleTestCase):
    def test_pot_and_ldr(self):
        self.chip.volts[:2] = [1.65, 1.65]
        _, out, exc = self.run_example("03_light_and_pot.py")
        self.assertIsNone(exc)
        self.assertRegex(out.splitlines()[0], r"Pot  50\.0 %.*LDR +10\.0 k  light  50\.0 %")

    def test_dark_and_bright(self):
        self.chip.volts[1] = 3.3
        _, out, _ = self.run_example("03_light_and_pot.py")
        self.assertNotIn("full-scale", out)
        self.assertIn("LDR open  light   0.0 %", out)
        self.chip.volts[1] = 0.0
        _, out, _ = self.run_example("03_light_and_pot.py")
        self.assertIn("light 100.0 %", out)


class TestLightAndPotRange(_ExampleTestCase):
    def test_over_range_is_reported(self):
        self.chip.volts[0] = 5.0
        _, out, exc = self.run_example("03_light_and_pot.py")
        self.assertIsNone(exc)
        self.assertIn("CH0 is at the ±4.096 V full-scale limit", out)


class TestMultipleBoards(_ExampleTestCase):
    def test_finds_and_reads_every_board(self):
        self.chips[0x4A] = fakes.ADS1115Chip([0.5, 0.6, 0.7, 0.8])
        _, out, exc = self.run_example("04_multiple_boards.py")
        self.assertIsNone(exc)
        self.assertIn("Found board at 0x48", out)
        self.assertIn("Found board at 0x4A", out)
        self.assertNotIn("0x49", out)
        self.assertIn("0x48: 1.000 1.650 2.500 3.000  |  0x4A: 0.500 0.600 0.700 0.800", out)

    def test_all_four(self):
        for addr in (0x49, 0x4A, 0x4B):
            self.chips[addr] = fakes.ADS1115Chip(VOLTS)
        _, out, _ = self.run_example("04_multiple_boards.py", loops=1)
        self.assertEqual(out.count("Found board"), 4)
        self.assertEqual(out.splitlines()[-1].count("|"), 3)

    def test_no_boards(self):
        self.chips.clear()
        _, _, exc = self.run_example("04_multiple_boards.py")
        self.assertIsInstance(exc, SystemExit)
        self.assertIn("No boards found: Check the wiring", str(exc))

    def test_over_range_channel(self):
        self.chip.volts[1] = 5.0
        _, out, _ = self.run_example("04_multiple_boards.py", loops=1)
        self.assertIn("0x48: 1.000  over 2.500 3.000", out)


class TestCsvLogger(_ExampleTestCase):
    def read_csv(self, path):
        with open(path, newline="") as f:
            return list(csv.reader(f))

    def test_defaults(self):
        _, out, exc = self.run_example("05_csv_logger.py")
        self.assertIsNone(exc)
        self.assertIn("Logging every 5 s to ads_log.csv", out)
        rows = self.read_csv(os.path.join(self.dir, "ads_log.csv"))
        self.assertEqual(rows[0], ["timestamp", "ch0_V", "ch1_V", "ch2_V", "ch3_V"])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1][1:], ["1.00000", "1.65000", "2.50000", "3.00000"])
        self.assertRegex(rows[1][0], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$")

    def test_arguments_and_interval(self):
        path = os.path.join(self.dir, "garden.csv")
        _, out, _ = self.run_example("05_csv_logger.py", ["60", path])
        self.assertIn("Logging every 60 s", out)
        self.assertTrue(os.path.exists(path))
        interval = self.sleep.call_args_list[0].args[0]
        self.assertTrue(59 < interval <= 60, interval)

    def test_appends_without_second_header(self):
        path = os.path.join(self.dir, "log.csv")
        self.run_example("05_csv_logger.py", ["1", path])
        self.run_example("05_csv_logger.py", ["1", path])
        rows = self.read_csv(path)
        self.assertEqual((len(rows), sum(r[0] == "timestamp" for r in rows)), (5, 1))

    def test_invalid_reading_leaves_an_empty_cell(self):
        self.chip.volts[2] = 5.0
        path = os.path.join(self.dir, "log.csv")
        _, out, _ = self.run_example("05_csv_logger.py", ["1", path], loops=1)
        self.assertEqual(self.read_csv(path)[1][1:], ["1.00000", "1.65000", "", "3.00000"])
        self.assertIn("CH2 is at the ±4.096 V full-scale limit", out)

    def test_calibration_and_sample_count(self):
        self.write_cal({"3": 0.99})
        path = os.path.join(self.dir, "log.csv")
        self.run_example("05_csv_logger.py", ["1", path], loops=1)
        self.assertEqual(self.read_csv(path)[1][4], "2.97000")
        self.assertEqual(self.chip.conversions, 64)


class TestCalibrate(_ExampleTestCase):
    def calibrate(self, *argv):
        return self.run_example("06_calibrate.py", argv)

    def saved(self):
        with open(self.cal_path) as f:
            return json.load(f)

    def test_saves_factor(self):
        _, out, exc = self.calibrate("3", "3.003")
        self.assertIsNone(exc)
        self.assertEqual(self.saved(), {"3": 1.001})
        self.assertIn("CH3: Measured 3.00000 V, true 3.00300 V, factor 1.00100 saved", out)

    def test_slowest_rate_and_32_samples(self):
        self.calibrate("0", "1.0")
        self.assertEqual({c & fakes.DR_MASK for c in self.configs()}, {fakes.DR[8]})
        self.assertEqual(self.chip.conversions, 32)

    def test_keeps_other_channels(self):
        self.write_cal({"0": 1.002, "3": 0.5})
        self.calibrate("3", "2.997")
        self.assertEqual(self.saved(), {"0": 1.002, "3": 0.999})

    def test_usage(self):
        for argv in ((), ("0",), ("0", "1", "2")):
            with self.subTest(argv=argv):
                _, _, exc = self.calibrate(*argv)
                self.assertIsInstance(exc, SystemExit)
                self.assertIn("calibration", str(exc.code).lower())

    def test_rejects_bad_input(self):
        cases = [(("4", "3.0"), "Channel must be 0-3"), (("0", "0.2"), "Channel must be 0-3"),
                 (("0", "6.0"), "Channel must be 0-3")]
        self.chip.volts[2] = 0.01
        cases += [(("2", "3.3"), "Check the voltage is connected"), (("3", "3.2"), "outside ±3 %")]
        self.chip.volts[1] = 5.0
        cases += [(("1", "5.0"), "CH1 is at the ±4.096 V full-scale limit")]
        for argv, message in cases:
            with self.subTest(argv=argv):
                _, _, exc = self.calibrate(*argv)
                self.assertIn(message, str(exc))
                self.assertFalse(os.path.exists(self.cal_path))


class TestBoardNotAnswering(_ExampleTestCase):
    """Every example stops with the library's message when the board does not answer."""

    def test_message(self):
        self.chips.clear()
        for name, argv in (("01_read_all_channels.py", ()), ("02_thermistor_ntc.py", ()),
                           ("03_light_and_pot.py", ()), ("05_csv_logger.py", ("1", "x.csv")),
                           ("06_calibrate.py", ("0", "1.0"))):
            with self.subTest(example=name):
                _, _, exc = self.run_example(name, argv)
                self.assertIsInstance(exc, SystemExit)
                self.assertIn("No answer from the board at 0x48", str(exc))
                self.assertIn("Check the J1 wiring", str(exc))


class TestMockOption(_ExampleTestCase):
    """Every example runs with --mock and no smbus2 or hardware at all."""

    def run_mock(self, name, *argv, loops=2):
        side_effect = [None] * (loops - 1) + [KeyboardInterrupt]
        with mock.patch("time.sleep", side_effect=side_effect):
            return fakes.run_script(os.path.join(fakes.PY_DIR, name), [*argv, "--mock"],
                                    {"smbus2": None}, cwd=self.dir)

    def test_read_all_channels(self):
        _, out, exc = self.run_mock("01_read_all_channels.py")
        self.assertIsNone(exc)
        self.assertIn(" 13200  1.650V   13200  1.650V   20000  2.500V   24000  3.000V", out)

    def test_thermistor(self):
        _, out, exc = self.run_mock("02_thermistor_ntc.py")
        self.assertIsNone(exc)
        self.assertIn("T= 25.00 C", out)

    def test_light_and_pot(self):
        _, out, _ = self.run_mock("03_light_and_pot.py")
        self.assertIn("Pot  50.0 %", out)

    def test_multiple_boards(self):
        _, out, exc = self.run_mock("04_multiple_boards.py")
        self.assertIsNone(exc)
        self.assertIn("Found board at 0x48\nFound board at 0x49", out)

    def test_csv_logger(self):
        _, out, exc = self.run_mock("05_csv_logger.py", "2", "mock.csv")
        self.assertIsNone(exc)
        self.assertIn("Logging every 2 s to mock.csv", out)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "mock.csv")))

    def test_calibrate(self):
        _, out, exc = self.run_mock("06_calibrate.py", "3", "3.003")
        self.assertIsNone(exc)
        self.assertIn("factor 1.00100 saved", out)
        _, _, exc = self.run_mock("06_calibrate.py")
        self.assertIn("calibration", str(exc.code).lower())   # --mock alone is not an argument


if __name__ == "__main__":
    unittest.main()
