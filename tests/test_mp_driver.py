"""Unit tests for micropython/ads1115.py, run on CPython against a register-level ADS1115
model with a fake MicroPython `time` module."""
import unittest

import fakes
from fakes import DR, DR_MASK, MODE_SINGLE, MUX_DIFF, MUX_MASK, MUX_SINGLE, OS, PGA, PGA_MASK, QUE_MASK


class _MPTestCase(unittest.TestCase):
    volts = (1.0, 1.65, 0.2, 3.0)
    chip_kwargs = {}

    def setUp(self):
        self.time = fakes.MicroPythonTime()
        self.mod = fakes.load_mp_driver(self.time)
        self.chip = fakes.ADS1115Chip(self.volts, **self.chip_kwargs)
        self.bus = fakes.FakeI2C({0x48: self.chip})
        self.adc = self.mod.ADS1115(self.bus)

    def last_config(self):
        return self.chip.config_writes()[-1]

    def lsb(self, fsr=None):
        return (fsr or self.adc.fsr) / 32768


class TestConstructor(_MPTestCase):
    def test_defaults(self):
        self.assertIs(self.adc.i2c, self.bus)
        self.assertEqual((self.adc.address, self.adc.fsr, self.adc.rate), (0x48, 4.096, 128))
        self.assertEqual(self.chip.writes, [])

    def test_every_valid_setting(self):
        for address in (0x48, 0x49, 0x4A, 0x4B):
            for fsr in PGA:
                for rate in DR:
                    adc = self.mod.ADS1115(self.bus, address=address, fsr=fsr, rate=rate)
                    self.assertEqual((adc.address, adc.fsr, adc.rate), (address, fsr, rate))

    def test_invalid_settings(self):
        for kwargs, word in ((dict(address=0x50), "address"), (dict(fsr=5.0), "fsr"), (dict(rate=100), "rate")):
            with self.subTest(**kwargs), self.assertRaisesRegex(ValueError, word):
                self.mod.ADS1115(self.bus, **kwargs)


class TestConfigWord(_MPTestCase):
    def test_default_read(self):
        self.adc.read_raw(0)
        self.assertEqual(self.last_config(), 0xC383)

    def test_mux(self):
        for ch, mux in MUX_SINGLE.items():
            self.adc.read_raw(ch)
            self.assertEqual(self.last_config() & MUX_MASK, mux)
        for pair, mux in MUX_DIFF.items():
            self.adc.read_differential(*pair)
            self.assertEqual(self.last_config() & MUX_MASK, mux)

    def test_gain_and_rate_bits(self):
        for fsr, pga in PGA.items():
            for rate, dr in DR.items():
                self.adc.fsr, self.adc.rate = fsr, rate
                self.adc.read_raw(0)
                self.assertEqual(self.last_config() & (PGA_MASK | DR_MASK), pga | dr)

    def test_single_shot_start_bit_comparator_off(self):
        self.adc.read_voltage(1, samples=2)
        self.adc.read_differential(0, 1)
        for cfg in self.chip.config_writes():
            self.assertTrue(cfg & OS and cfg & MODE_SINGLE)
            self.assertEqual(cfg & QUE_MASK, 0x3)


class TestReads(_MPTestCase):
    def test_each_channel_and_range(self):
        for ch, v in enumerate(self.volts):
            self.assertAlmostEqual(self.adc.read_voltage(ch), v, delta=self.lsb())
        for fsr in PGA:
            self.adc.fsr = fsr
            self.chip.volts[0] = fsr * 0.6
            self.assertAlmostEqual(self.adc.read_voltage(0), fsr * 0.6, delta=self.lsb(fsr))

    def test_sign_and_full_scale(self):
        self.chip.volts[0] = -0.001
        self.assertEqual(self.adc.read_raw(0), -8)
        self.chip.volts[0] = 5.0
        self.assertEqual(self.adc.read_raw(0), 32767)
        self.chip.volts[0] = -5.0
        self.assertEqual(self.adc.read_raw(0), -32768)

    def test_averaging_and_differential(self):
        self.assertAlmostEqual(self.adc.read_voltage(1, samples=16), 1.65, delta=self.lsb())
        self.assertEqual(self.chip.conversions, 16)
        self.assertAlmostEqual(self.adc.read_differential(2, 3), -2.8, delta=self.lsb())
        self.assertAlmostEqual(self.adc.read_differential(0, 1, samples=3), -0.65, delta=self.lsb())

    def test_invalid_arguments(self):
        for call in (lambda: self.adc.read_raw(4), lambda: self.adc.read_voltage(4),
                     lambda: self.adc.read_differential(1, 2)):
            with self.assertRaises(ValueError):
                call()

    def test_missing_board(self):
        adc = self.mod.ADS1115(self.bus, address=0x49)
        with self.assertRaises(self.mod.BusError) as cm:
            adc.read_voltage(0)
        self.assertIsInstance(cm.exception, OSError)
        self.assertIn("No answer from the board at 0x49", str(cm.exception))
        self.bus.chips[0x49] = fakes.ADS1115Chip([0.7] * 4)
        self.assertAlmostEqual(adc.read_voltage(0), 0.7, delta=self.lsb())


class TestConversionWait(_MPTestCase):
    chip_kwargs = {"busy_polls": 3}

    def test_wait_then_poll(self):
        for rate in (8, 860):
            self.time.slept_us.clear()
            self.adc.rate = rate
            self.adc.read_raw(0)
            self.assertGreaterEqual(self.time.slept_us[0], 1_000_000 / rate)
        self.assertEqual(self.chip.config_reads, 8)      # 4 per read

    def test_gives_up_after_100_polls(self):
        self.chip.never_ready = True
        self.assertAlmostEqual(self.adc.read_voltage(0), 1.0, delta=self.lsb())
        self.assertEqual(self.chip.config_reads, 100)


class TestInputRange(_MPTestCase):
    def test_full_scale_raises_and_next_read_works(self):
        self.chip.volts[2] = 5.0
        with self.assertRaises(self.mod.InputRangeError) as cm:
            self.adc.read_voltage(2, samples=2)
        self.assertIsInstance(cm.exception, ValueError)
        self.assertIn("ADS1115(i2c, fsr=6.144) on a board powered from 5 V", str(cm.exception))
        self.assertEqual(self.adc.read_raw(2), 32767)
        self.adc.start(2)
        with self.assertRaisesRegex(self.mod.InputRangeError, "CH2"):
            self.adc.result_voltage()
        self.adc.fsr = 6.144
        self.assertAlmostEqual(self.adc.read_voltage(2), 5.0, delta=self.lsb(6.144))
        self.chip.volts[2] = 7.0
        with self.assertRaisesRegex(self.mod.InputRangeError, "Keep every input"):
            self.adc.read_voltage(2)

    def test_differential(self):
        self.adc.fsr = 2.048
        with self.assertRaisesRegex(self.mod.InputRangeError, "CH2−CH3"):
            self.adc.read_differential(2, 3)


class TestMockI2C(unittest.TestCase):
    def setUp(self):
        self.mod = fakes.load_mp_driver(fakes.MicroPythonTime())

    def test_default_board(self):
        i2c = self.mod.MockI2C()
        self.assertEqual(i2c.scan(), [0x48])
        adc = self.mod.ADS1115(i2c)
        self.assertEqual([round(adc.read_voltage(ch), 3) for ch in range(4)], [1.65, 1.65, 2.5, 3.0])

    def test_voltages_addresses_and_errors(self):
        i2c = self.mod.MockI2C(volts=(0.1, 0.2, 0.3, 0.4), addresses=(0x48, 0x4B))
        self.assertEqual(i2c.scan(), [0x48, 0x4B])
        i2c.volts[0x4B][2] = 0.75
        adc = self.mod.ADS1115(i2c, address=0x4B, fsr=1.024)
        self.assertAlmostEqual(adc.read_voltage(2), 0.75, delta=1.024 / 32768)
        self.assertAlmostEqual(adc.read_differential(0, 1), -0.1, delta=1.024 / 32768)
        with self.assertRaises(self.mod.BusError):
            self.mod.ADS1115(i2c, address=0x49).read_voltage(0)
        adc.enable_ready_pin()
        adc.start(2)
        self.assertAlmostEqual(adc.result_voltage(), 0.75, delta=1.024 / 32768)

    def test_matches_the_pi_mock(self):
        pkg, _ = fakes.load_pi_driver()
        self.assertEqual(tuple(self.mod.MockI2C().volts[0x48]), pkg.DEFAULT_VOLTS)


class TestReadyPin(_MPTestCase):
    def test_ready_mode_and_start(self):
        pulses = []
        self.chip.on_ready = lambda: pulses.append(1)
        self.adc.enable_ready_pin()
        self.adc.start(1)
        self.assertTrue(self.chip.rdy_enabled())
        self.assertEqual(len(pulses), 1)
        self.assertEqual((self.chip.config_reads, self.time.slept_us), (0, []))
        self.assertAlmostEqual(self.adc.result_voltage(), 1.65, delta=self.lsb())


class TestSameApiAsPi(unittest.TestCase):
    """The two drivers must stay interchangeable."""

    def test_tables_and_methods_match(self):
        pkg, drv = fakes.load_pi_driver()
        mod = fakes.load_mp_driver(fakes.MicroPythonTime())
        for table in ("_PGA", "_DR", "_MUX_SINGLE", "_MUX_DIFF", "_OS_START", "_MODE_SINGLE",
                      "_COMP_DISABLE", "_COMP_ASSERT_1"):
            with self.subTest(table=table):
                self.assertEqual(getattr(drv, table), getattr(mod, table))
        for name in ("ADDRESSES", "BusError", "InputRangeError"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(mod, name) and hasattr(pkg, name))
        self.assertEqual(mod.ADDRESSES, pkg.ADDRESSES)
        self.assertTrue(issubclass(mod.BusError, OSError) and issubclass(pkg.BusError, OSError))
        self.assertTrue(issubclass(mod.InputRangeError, ValueError) and issubclass(pkg.InputRangeError, ValueError))
        public = lambda cls: {n for n in vars(cls) if not n.startswith("_")}
        self.assertLessEqual(public(mod.ADS1115), public(pkg.ADS1115))
        import inspect
        for name in public(mod.ADS1115):
            with self.subTest(method=name):
                mp = list(inspect.signature(getattr(mod.ADS1115, name)).parameters)
                pi = list(inspect.signature(getattr(pkg.ADS1115, name)).parameters)
                self.assertEqual(mp, pi)


if __name__ == "__main__":
    unittest.main()
