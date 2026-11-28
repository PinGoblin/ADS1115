"""Tests for the MicroPython examples in micropython/, with fake `machine` and `time` modules
and a register-level ADS1115."""
import math
import os
import unittest

import fakes

pkg, _ = fakes.load_pi_driver()


class _MPExample(unittest.TestCase):
    script = None

    def setUp(self):
        self.chip = fakes.ADS1115Chip([1.65, 0.5, 1.0, 3.0])
        self.chips = {0x48: self.chip}

    def run_example(self, loops=2):
        self.time = fakes.MicroPythonTime(sleep_limit=loops)
        self.machine = fakes.make_machine(fakes.FakeI2C(self.chips))
        modules = {"time": self.time, "machine": self.machine, "ads1115": fakes.load_mp_driver(self.time)}
        return fakes.run_script(os.path.join(fakes.MP_DIR, self.script), (), modules)


class TestMain(_MPExample):
    script = "main.py"

    def test_prints_temperature_and_voltages(self):
        _, out, exc = self.run_example()
        self.assertIsInstance(exc, fakes.StopScript)    # endless loop, stopped by the fake sleep
        lines = out.splitlines()
        self.assertEqual(lines[0], "I2C devices: ['0x48']")
        self.assertEqual(len(lines), 3)
        self.assertRegex(lines[1], r"^T=25\.0\d C   CH1=0\.500 V  CH2=1\.000 V  CH3=3\.000 V$")

    def test_esp32_pins_at_100_khz(self):
        self.run_example(loops=1)
        self.assertEqual(self.machine.i2c_calls, [{"id": 0, "scl": 22, "sda": 21, "freq": 100_000}])

    def test_four_samples_per_channel(self):
        self.run_example(loops=1)
        self.assertEqual(self.chip.conversions, 16)
        self.assertEqual(self.time.sleeps, [1])

    def test_open_or_shorted_thermistor(self):
        for v in (3.3, 3.2995, 3.31, 0.0):
            self.chip.volts[0] = v
            with self.subTest(v=v):
                _, out, _ = self.run_example(loops=1)
                self.assertIn("T=--.- C", out)

    def test_zero_volts_says_close_the_res_jumper(self):
        self.chip.volts[0] = 0.0
        _, out, _ = self.run_example(loops=1)
        self.assertIn("CH0 reads 0 V: Close the RES jumper JP5", out)
        self.chip.volts[0] = 1.65
        _, out, _ = self.run_example(loops=1)
        self.assertNotIn("reads 0 V", out)

    def test_full_scale_warning(self):
        self.chip.volts[0] = 4.5
        self.chip.volts[3] = 4.5
        _, out, _ = self.run_example(loops=1)
        self.assertIn("CH0 is at the ±4.096 V full-scale limit", out)
        self.assertIn("fsr=6.144", out)
        self.assertIn("T=--.- C", out)
        self.assertIn("CH3=over V", out)
        self.chip.volts[0], self.chip.volts[3] = 1.65, 3.0
        _, out, _ = self.run_example(loops=1)
        self.assertNotIn("full-scale", out)

    def test_board_stops_answering(self):
        original = self.chip.read
        calls = [0]

        def read(reg):
            calls[0] += 1
            if calls[0] > 10:
                raise OSError(19, "ENODEV")
            return original(reg)
        self.chip.read = read
        _, out, exc = self.run_example()
        self.assertIsInstance(exc, SystemExit)
        self.assertIn("No answer from the board at 0x48", str(exc))

    def test_mock_needs_no_hardware(self):
        self.time = fakes.MicroPythonTime(sleep_limit=2)
        modules = {"time": self.time, "machine": None, "ads1115": fakes.load_mp_driver(self.time)}
        _, out, exc = fakes.run_script(os.path.join(fakes.MP_DIR, self.script), ["--mock"], modules)
        self.assertIsInstance(exc, fakes.StopScript)
        self.assertIn("I2C devices: ['0x48']", out)
        self.assertRegex(out, r"T=25\.0\d C   CH1=1\.650 V  CH2=2\.500 V  CH3=3\.000 V")

    def test_board_not_found(self):
        self.chips = {0x49: self.chip}
        _, out, exc = self.run_example()
        self.assertIsInstance(exc, SystemExit)
        self.assertIn("No board found at 0x48: Check the wiring", str(exc))
        self.assertIn("['0x49']", out)

    def test_matches_raspberry_pi_maths(self):
        g, _, _ = self.run_example(loops=1)
        self.assertEqual(g["R_EXC"], pkg.R_EXCITATION)
        for v in (0.3, 0.8, 1.2, 1.65, 2.2, 2.9, 3.2):
            with self.subTest(v=v):
                expected = pkg.ntc_celsius(pkg.resistance_from_voltage(v, g["VDD"]), g["R0"], g["T0_C"], g["BETA"])
                self.assertAlmostEqual(g["ntc_celsius"](v), expected, places=9)
        r = 10_000 * math.exp(3950 * (1 / 233.15 - 1 / 298.15))     # −40 °C is not "open"
        self.assertAlmostEqual(g["ntc_celsius"](g["VDD"] * r / (r + 10_000)), -40.0, places=6)


class TestReadyPinFast(_MPExample):
    script = "ready_pin_fast.py"

    def setUp(self):
        super().setUp()
        self.chip.volts[0] = 1.234
        self.wired = True
        self.chip.on_ready = self.pulse_rdy

    def pulse_rdy(self):
        pin = self.machine.pins.get(4)
        if self.wired and pin:
            pin.fire()

    def test_collects_samples(self):
        g, out, exc = self.run_example()
        self.assertIsNone(exc)
        n = len(g["samples"])
        self.assertGreater(n, 100)
        self.assertIn("%d samples in 2 s" % n, out)
        self.assertIn("mean 1.2340 V  min 1.2340 V  max 1.2340 V", out)
        self.assertEqual(self.chip.conversions, n + 1)    # the last one is started, never read
        self.assertEqual(self.chip.config_reads, 0)       # relies on RDY, never polls

    def test_settings(self):
        self.run_example()
        self.assertEqual(self.machine.i2c_calls[0]["freq"], 100_000)
        self.assertEqual(self.chip.config_writes()[-1] & fakes.DR_MASK, fakes.DR[860])
        self.assertTrue(self.chip.rdy_enabled())
        pin = self.machine.pins[4]
        self.assertEqual((pin.trigger, pin.pull), (self.machine.Pin.IRQ_FALLING, self.machine.Pin.PULL_UP))

    def test_rdy_not_wired(self):
        self.wired = False
        _, out, _ = self.run_example()
        self.assertIn("No ready pulses: Check the RDY wire from J1 pin 5 to GPIO4", out)

    def test_over_range_readings_are_counted(self):
        self.chip.volts[0] = 5.0
        _, out, _ = self.run_example()
        self.assertRegex(out, r"^\d+ readings beyond the ±4\.096 V range: Use a larger fsr")
        self.assertNotIn("No ready pulses", out)

    def test_missing_board(self):
        self.chips = {}
        _, _, exc = self.run_example()
        self.assertIn("No answer from the board at 0x48", str(exc))

    def test_mock_needs_no_hardware(self):
        self.time = fakes.MicroPythonTime()
        modules = {"time": self.time, "machine": None, "ads1115": fakes.load_mp_driver(self.time)}
        g, out, exc = fakes.run_script(os.path.join(fakes.MP_DIR, self.script), ["--mock"], modules)
        self.assertIsNone(exc)
        self.assertGreater(len(g["samples"]), 100)
        self.assertIn("mean 1.6500 V", out)


if __name__ == "__main__":
    unittest.main()
