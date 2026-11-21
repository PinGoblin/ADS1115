"""Tests for the Raspberry Pi example scripts in python/, using a fake Adafruit library."""
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

sys.path.insert(0, fakes.PY_DIR)
import breakout_ads  # noqa: E402

VOLTS = [1.0, 1.65, 2.5, 3.0]


class _ExampleTestCase(unittest.TestCase):
    """Runs an example with a fake board; `time.sleep` stops the loop after `loops` passes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cal_path = os.path.join(self.tmp.name, "calibration.json")
        patcher = mock.patch.object(breakout_ads, "CAL_FILE", self.cal_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.boards = {0x48: list(VOLTS)}

    def run_example(self, name, argv=(), loops=2, layout=3, edits=None):
        self.fake = fakes.FakeAdafruit(self.boards, layout=layout)
        modules = {**self.fake.modules(), "breakout_ads": breakout_ads}
        side_effect = [None] * (loops - 1) + [KeyboardInterrupt]
        with mock.patch("time.sleep", side_effect=side_effect) as sleep:
            result = fakes.run_script(os.path.join(fakes.PY_DIR, name), argv, modules,
                                      cwd=self.tmp.name, edits=edits)
        self.sleep = sleep
        return result

    def write_cal(self, cal):
        with open(self.cal_path, "w") as f:
            json.dump(cal, f)

    def data_lines(self, out):
        return [line for line in out.splitlines() if re.search(r"\d", line)]


class TestReadAllChannels(_ExampleTestCase):
    def test_prints_counts_and_volts(self):
        _, out, exc = self.run_example("01_read_all_channels.py")
        self.assertIsNone(exc)                       # Ctrl+C exits cleanly
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("CH0 (J2)"))
        self.assertEqual(len(lines), 3)              # header + one line per loop
        self.assertEqual(re.findall(r"(\d+)\s+(\d\.\d{3})V", lines[1]),
                         [("8000", "1.000"), ("13200", "1.650"), ("20000", "2.500"), ("24000", "3.000")])

    def test_settings(self):
        g, _, _ = self.run_example("01_read_all_channels.py")
        ads = self.fake.devices[0]
        self.assertEqual((ads.address, ads.gain), (0x48, 1))
        self.sleep.assert_called_with(0.5)

    def test_applies_calibration(self):
        self.write_cal({"0": 1.01})
        _, out, _ = self.run_example("01_read_all_channels.py")
        self.assertIn("1.010V", out.splitlines()[1])

    def test_library_2(self):
        _, out, exc = self.run_example("01_read_all_channels.py", layout=2)
        self.assertIsNone(exc)
        self.assertIn("3.000V", out)


class TestThermistor(_ExampleTestCase):
    def test_temperature_line(self):
        self.boards[0x48][0] = 1.65                  # 10 kΩ = 25 °C
        _, out, exc = self.run_example("02_thermistor_ntc.py")
        self.assertIsNone(exc)
        self.assertIn("R= 10.000 k", out)
        self.assertIn("T= 25.00 C", out)
        self.assertIn("VDD=3.300 V", out)

    def test_averages_sixteen_samples(self):
        self.run_example("02_thermistor_ntc.py", loops=1)
        self.assertEqual(self.fake.reads, 16)

    def test_open_circuit(self):
        # Exactly VDD, a hair below it (ADC noise), and above it (VDD set slightly low)
        for v in (3.3, 3.2995, 3.31):
            self.boards[0x48][0] = v
            with self.subTest(v=v):
                _, out, _ = self.run_example("02_thermistor_ntc.py")
                self.assertIn("Open circuit", out)
                self.assertNotIn("T=", out)

    def test_cold_thermistor_is_not_open(self):
        r = 10_000 * math.exp(3950 * (1 / 233.15 - 1 / 298.15))   # -40 C, about 278 k
        self.boards[0x48][0] = 3.3 * r / (r + 10_000)
        _, out, _ = self.run_example("02_thermistor_ntc.py")
        self.assertIn("T=-40.00 C", out)

    def test_short_circuit(self):
        self.boards[0x48][0] = 0.0
        _, out, _ = self.run_example("02_thermistor_ntc.py")
        self.assertIn("Short circuit", out)

    def test_live_vdd_measurement(self):
        self.boards[0x48][0] = 1.6                  # half of a 3.2 V supply -> 10 kΩ
        self.boards[0x48][3] = 3.2                  # CH3 VDD linked to SIG
        _, out, _ = self.run_example("02_thermistor_ntc.py",
                                     edits={"VDD_CHANNEL = None": "VDD_CHANNEL = 3"})
        self.assertIn("VDD=3.200 V", out)
        self.assertIn("T= 25.00 C", out)

    def test_applies_calibration(self):
        self.boards[0x48][0] = 1.5
        self.write_cal({"0": 1.1})                   # 1.5 V × 1.1 = 1.65 V -> 25 °C
        _, out, _ = self.run_example("02_thermistor_ntc.py")
        self.assertIn("V=1.6500 V", out)
        self.assertIn("T= 25.00 C", out)


class TestLightAndPot(_ExampleTestCase):
    def test_pot_and_ldr(self):
        self.boards[0x48][:2] = [1.65, 1.65]
        _, out, exc = self.run_example("03_light_and_pot.py")
        self.assertIsNone(exc)
        line = out.splitlines()[0]
        self.assertIn("Pot  50.0 %", line)
        self.assertIn("LDR     10.0 k", line)
        self.assertIn("light  50.0 %", line)

    def test_dark_ldr_reads_open(self):
        self.boards[0x48][1] = 3.3
        _, out, _ = self.run_example("03_light_and_pot.py")
        self.assertIn("LDR open", out)
        self.assertIn("light   0.0 %", out)

    def test_bright_ldr(self):
        self.boards[0x48][1] = 0.0
        _, out, _ = self.run_example("03_light_and_pot.py")
        self.assertIn("light 100.0 %", out)


class TestMultipleBoards(_ExampleTestCase):
    def test_finds_every_board(self):
        self.boards = {0x48: list(VOLTS), 0x4A: [0.5, 0.6, 0.7, 0.8]}
        _, out, exc = self.run_example("04_multiple_boards.py")
        self.assertIsNone(exc)
        self.assertIn("Found board at 0x48", out)
        self.assertIn("Found board at 0x4A", out)
        self.assertNotIn("0x49", out)
        self.assertIn("0x48: 1.000 1.650 2.500 3.000  |  0x4A: 0.500 0.600 0.700 0.800", out)

    def test_all_four_addresses(self):
        self.boards = {addr: list(VOLTS) for addr in (0x48, 0x49, 0x4A, 0x4B)}
        _, out, _ = self.run_example("04_multiple_boards.py", loops=1)
        self.assertEqual(out.count("Found board"), 4)
        self.assertEqual(out.splitlines()[-1].count("|"), 3)

    def test_no_boards(self):
        self.boards = {}
        _, out, exc = self.run_example("04_multiple_boards.py")
        self.assertIsInstance(exc, SystemExit)
        self.assertIn("No boards found", str(exc))

    def test_board_that_fails_test_read_is_skipped(self):
        self.boards = {0x48: list(VOLTS), 0x49: [None] * 4}   # answers, then the read fails
        original = fakes.FakeAdafruit.__init__

        def failing_init(fake, boards, layout=3):
            original(fake, boards, layout)
            analog_in = fake.AnalogIn

            class Flaky(analog_in):
                @property
                def value(self):
                    if self.ads.address == 0x49:
                        raise OSError("remote I/O error")
                    return super().value
            fake.AnalogIn = Flaky

        with mock.patch.object(fakes.FakeAdafruit, "__init__", failing_init):
            _, out, _ = self.run_example("04_multiple_boards.py", loops=1)
        self.assertIn("Found board at 0x48", out)
        self.assertNotIn("Found board at 0x49", out)


class TestCsvLogger(_ExampleTestCase):
    def read_csv(self, path):
        with open(path, newline="") as f:
            return list(csv.reader(f))

    def test_default_file_and_interval(self):
        _, out, exc = self.run_example("05_csv_logger.py")
        self.assertIsNone(exc)
        self.assertIn("Logging every 5 s to ads_log.csv", out)
        rows = self.read_csv(os.path.join(self.tmp.name, "ads_log.csv"))
        self.assertEqual(rows[0], ["timestamp", "ch0_V", "ch1_V", "ch2_V", "ch3_V"])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1][1:], ["1.00000", "1.65000", "2.50000", "3.00000"])
        self.assertRegex(rows[1][0], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$")

    def test_arguments(self):
        path = os.path.join(self.tmp.name, "garden.csv")
        _, out, _ = self.run_example("05_csv_logger.py", ["60", path])
        self.assertIn("Logging every 60 s", out)
        self.assertTrue(os.path.exists(path))
        interval = self.sleep.call_args_list[0].args[0]
        self.assertGreater(interval, 59)
        self.assertLessEqual(interval, 60)

    def test_appends_without_second_header(self):
        path = os.path.join(self.tmp.name, "log.csv")
        self.run_example("05_csv_logger.py", ["1", path])
        self.run_example("05_csv_logger.py", ["1", path])
        rows = self.read_csv(path)
        self.assertEqual(len(rows), 5)
        self.assertEqual(sum(r[0] == "timestamp" for r in rows), 1)

    def test_applies_calibration(self):
        self.write_cal({"3": 0.99})
        path = os.path.join(self.tmp.name, "log.csv")
        self.run_example("05_csv_logger.py", ["1", path], loops=1)
        self.assertEqual(self.read_csv(path)[1][4], "2.97000")

    def test_averages_sixteen_samples_per_channel(self):
        self.run_example("05_csv_logger.py", ["1", os.path.join(self.tmp.name, "x.csv")], loops=1)
        self.assertEqual(self.fake.reads, 64)


class TestCalibrate(_ExampleTestCase):
    def calibrate(self, *argv):
        with mock.patch("time.sleep"):
            self.fake = fakes.FakeAdafruit(self.boards)
            modules = {**self.fake.modules(), "breakout_ads": breakout_ads}
            return fakes.run_script(os.path.join(fakes.PY_DIR, "06_calibrate.py"), argv, modules,
                                    cwd=self.tmp.name)

    def saved(self):
        with open(self.cal_path) as f:
            return json.load(f)

    def test_saves_factor(self):
        _, out, exc = self.calibrate("3", "3.003")
        self.assertIsNone(exc)
        self.assertEqual(self.saved(), {"3": 1.001})
        self.assertIn("CH3: measured 3.00000 V, true 3.00300 V -> factor 1.00100 saved", out)

    def test_uses_slowest_rate_and_32_samples(self):
        self.calibrate("0", "1.0")
        self.assertEqual(self.fake.devices[0].data_rate, 8)
        self.assertEqual(self.fake.reads, 32)

    def test_keeps_other_channels(self):
        self.write_cal({"0": 1.002, "3": 0.5})
        self.calibrate("3", "2.997")
        self.assertEqual(self.saved(), {"0": 1.002, "3": 0.999})

    def test_usage_message(self):
        for argv in ((), ("0",), ("0", "1", "2")):
            with self.subTest(argv=argv):
                _, _, exc = self.calibrate(*argv)
                self.assertIsInstance(exc, SystemExit)
                self.assertIn("one-point gain calibration", str(exc.code))

    def test_rejects_bad_channel_or_voltage(self):
        for argv in (("4", "3.0"), ("-1", "3.0"), ("0", "0.2"), ("0", "6.0")):
            with self.subTest(argv=argv):
                _, _, exc = self.calibrate(*argv)
                self.assertIn("Channel must be 0-3", str(exc))
                self.assertFalse(os.path.exists(self.cal_path))

    def test_rejects_unconnected_input(self):
        self.boards[0x48][2] = 0.01
        _, _, exc = self.calibrate("2", "3.3")
        self.assertIn("is the voltage connected", str(exc))
        self.assertFalse(os.path.exists(self.cal_path))

    def test_rejects_factor_beyond_three_percent(self):
        _, _, exc = self.calibrate("3", "3.2")
        self.assertIn("outside +/-3 %", str(exc))
        self.assertFalse(os.path.exists(self.cal_path))


if __name__ == "__main__":
    unittest.main()
