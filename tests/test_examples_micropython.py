"""Tests for the MicroPython example scripts in micropython/, with fake `machine` and `time`
modules and a register-level ADS1115."""
import math
import os
import sys
import unittest

import fakes

sys.path.insert(0, fakes.PY_DIR)
import breakout_ads  # noqa: E402


class _MicroPythonExample(unittest.TestCase):
    script = None

    def setUp(self):
        self.chip = fakes.ADS1115Chip([1.65, 0.5, 1.0, 3.0])
        self.chips = {0x48: self.chip}

    def run_example(self, loops=2, script=None):
        self.time = fakes.MicroPythonTime(sleep_limit=loops)
        self.machine = fakes.make_machine(fakes.FakeI2C(self.chips))
        modules = {"time": self.time, "machine": self.machine,
                   "ads1115": fakes.load_ads1115(self.time)}
        return fakes.run_script(os.path.join(fakes.MP_DIR, script or self.script), (), modules)


class TestMain(_MicroPythonExample):
    script = "main.py"

    def test_prints_temperature_and_voltages(self):
        _, out, exc = self.run_example()
        self.assertIsInstance(exc, fakes.StopScript)   # endless loop, stopped by the fake sleep
        lines = out.splitlines()
        self.assertEqual(lines[0], "I2C devices: ['0x48']")
        self.assertEqual(len(lines), 3)
        self.assertRegex(lines[1], r"^T=25\.0\d C   CH1=0\.500 V  CH2=1\.000 V  CH3=3\.000 V$")

    def test_default_esp32_pins(self):
        self.run_example(loops=1)
        self.assertEqual(self.machine.i2c_calls, [{"id": 0, "scl": 22, "sda": 21, "freq": 400_000}])

    def test_four_samples_per_channel(self):
        self.run_example(loops=1)
        self.assertEqual(self.chip.conversions, 16)
        self.assertEqual(self.time.sleeps, [1])

    def test_open_thermistor(self):
        for v in (3.3, 3.2995, 3.31):
            self.chip.volts[0] = v
            with self.subTest(v=v):
                _, out, _ = self.run_example(loops=1)
                self.assertIn("T=--.- C", out)

    def test_shorted_thermistor(self):
        self.chip.volts[0] = 0.0
        _, out, _ = self.run_example(loops=1)
        self.assertIn("T=--.- C", out)

    def test_board_not_found(self):
        self.chips = {0x49: self.chip}
        _, out, exc = self.run_example()
        self.assertIsInstance(exc, SystemExit)
        self.assertIn("not found at 0x48", str(exc))
        self.assertIn("['0x49']", out)

    def test_matches_raspberry_pi_maths(self):
        g, _, _ = self.run_example(loops=1)
        self.assertEqual(g["R_EXC"], breakout_ads.R_EXCITATION)
        for v in (0.3, 0.8, 1.2, 1.65, 2.2, 2.9, 3.2):
            with self.subTest(v=v):
                expected = breakout_ads.ntc_celsius(breakout_ads.resistance_from_voltage(v, g["VDD"]),
                                                    g["R0"], g["T0_C"], g["BETA"])
                self.assertAlmostEqual(g["ntc_celsius"](v), expected, places=9)

    def test_matches_beta_equation(self):
        g, _, _ = self.run_example(loops=1)
        r = 10_000 * math.exp(3950 * (1 / 273.15 - 1 / 298.15))       # 0 °C
        v = g["VDD"] * r / (r + 10_000)
        self.assertAlmostEqual(g["ntc_celsius"](v), 0.0, places=6)


class TestReadyPinFast(_MicroPythonExample):
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

    def test_one_conversion_per_sample(self):
        g, _, _ = self.run_example()
        # The final conversion is started but never read.
        self.assertEqual(self.chip.conversions, len(g["samples"]) + 1)
        self.assertEqual(self.chip.config_reads, 0)   # never polls, relies on RDY

    def test_fastest_rate_and_ready_mode(self):
        self.run_example()
        cfg = self.chip.config_writes()[-1]
        self.assertEqual(cfg & 0x00E0, 0x00E0)         # 860 SPS
        self.assertTrue(self.chip.rdy_enabled())

    def test_irq_on_gpio4_falling_edge(self):
        self.run_example()
        pin = self.machine.pins[4]
        self.assertEqual(pin.trigger, self.machine.Pin.IRQ_FALLING)
        self.assertEqual(pin.pull, self.machine.Pin.PULL_UP)
        self.assertIsNotNone(pin.handler)

    def test_rdy_not_wired(self):
        self.wired = False
        _, out, _ = self.run_example()
        self.assertIn("No ready pulses", out)


if __name__ == "__main__":
    unittest.main()
