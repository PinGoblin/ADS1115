"""Unit tests for micropython/ads1115.py (the MicroPython module), run on CPython
against a register-level model of the ADS1115."""
import unittest

import fakes
from fakes import REG_CONFIG, REG_HI_THRESH, REG_LO_THRESH

# Config register fields from the datasheet, written out independently of the module.
OS = 0x8000
MUX_SINGLE = {0: 0x4000, 1: 0x5000, 2: 0x6000, 3: 0x7000}
MUX_DIFF = {(0, 1): 0x0000, (0, 3): 0x1000, (1, 3): 0x2000, (2, 3): 0x3000}
PGA = {6.144: 0x0000, 4.096: 0x0200, 2.048: 0x0400, 1.024: 0x0600, 0.512: 0x0800, 0.256: 0x0A00}
DR = {8: 0x0000, 16: 0x0020, 32: 0x0040, 64: 0x0060, 128: 0x0080, 250: 0x00A0, 475: 0x00C0, 860: 0x00E0}
MODE_SINGLE = 0x0100
COMP_QUE_DISABLE = 0x0003
MUX_MASK, PGA_MASK, DR_MASK = 0x7000, 0x0E00, 0x00E0


class _DriverTestCase(unittest.TestCase):
    volts = (1.0, 1.65, 0.2, 3.0)
    chip_kwargs = {}

    def setUp(self):
        self.time = fakes.MicroPythonTime()
        self.mod = fakes.load_ads1115(self.time)
        self.chip = fakes.ADS1115Chip(self.volts, **self.chip_kwargs)
        self.bus = fakes.FakeI2C({0x48: self.chip})
        self.adc = self.mod.ADS1115(self.bus)

    def last_config(self):
        return self.chip.config_writes()[-1]

    def lsb(self, fsr=None):
        return (fsr or self.adc.fsr) / 32768


class TestConstructor(_DriverTestCase):
    def test_defaults(self):
        self.assertIs(self.adc.i2c, self.bus)
        self.assertEqual((self.adc.address, self.adc.fsr, self.adc.rate), (0x48, 4.096, 128))

    def test_no_bus_traffic(self):
        self.assertEqual(self.chip.writes, [])
        self.assertEqual(self.chip.config_reads, 0)

    def test_every_valid_range_and_rate(self):
        for fsr in PGA:
            for rate in DR:
                with self.subTest(fsr=fsr, rate=rate):
                    adc = self.mod.ADS1115(self.bus, fsr=fsr, rate=rate)
                    self.assertEqual((adc.fsr, adc.rate), (fsr, rate))

    def test_invalid_range(self):
        for fsr in (5.0, 3.3, 0, 8.192):
            with self.subTest(fsr=fsr), self.assertRaisesRegex(ValueError, "fsr"):
                self.mod.ADS1115(self.bus, fsr=fsr)

    def test_invalid_rate(self):
        for rate in (0, 100, 1000, 3300):
            with self.subTest(rate=rate), self.assertRaisesRegex(ValueError, "rate"):
                self.mod.ADS1115(self.bus, rate=rate)


class TestConfigWord(_DriverTestCase):
    def test_default_single_ended_read(self):
        self.adc.read_raw(0)
        self.assertEqual(self.last_config(), 0xC383)   # OS, AIN0, ±4.096 V, single-shot, 128 SPS, comparator off

    def test_channel_mux(self):
        for ch, mux in MUX_SINGLE.items():
            with self.subTest(ch=ch):
                self.adc.read_raw(ch)
                self.assertEqual(self.last_config() & MUX_MASK, mux)

    def test_differential_mux(self):
        for pair, mux in MUX_DIFF.items():
            with self.subTest(pair=pair):
                self.adc.read_differential(*pair)
                self.assertEqual(self.last_config() & MUX_MASK, mux)

    def test_gain_bits(self):
        for fsr, bits in PGA.items():
            with self.subTest(fsr=fsr):
                self.adc.fsr = fsr
                self.adc.read_raw(0)
                self.assertEqual(self.last_config() & PGA_MASK, bits)

    def test_rate_bits(self):
        for rate, bits in DR.items():
            with self.subTest(rate=rate):
                self.adc.rate = rate
                self.adc.read_raw(0)
                self.assertEqual(self.last_config() & DR_MASK, bits)

    def test_every_read_is_single_shot_with_start_bit(self):
        self.adc.read_raw(0)
        self.adc.read_differential(0, 1)
        self.adc.start(2)
        for cfg in self.chip.config_writes():
            self.assertTrue(cfg & OS)
            self.assertTrue(cfg & MODE_SINGLE)

    def test_comparator_disabled_by_default(self):
        self.adc.read_raw(0)
        self.assertEqual(self.last_config() & 0x3, COMP_QUE_DISABLE)

    def test_address_is_used(self):
        chip = fakes.ADS1115Chip([0.5] * 4)
        bus = fakes.FakeI2C({0x4A: chip})
        adc = self.mod.ADS1115(bus, address=0x4A)
        self.assertAlmostEqual(adc.read_voltage(0), 0.5, delta=self.lsb())
        self.assertEqual(chip.conversions, 1)


class TestReads(_DriverTestCase):
    def test_read_voltage_each_channel(self):
        for ch, v in enumerate(self.volts):
            with self.subTest(ch=ch):
                self.assertAlmostEqual(self.adc.read_voltage(ch), v, delta=self.lsb())

    def test_read_voltage_every_range(self):
        for fsr in PGA:
            self.adc.fsr = fsr
            v = fsr * 0.6
            self.chip.volts[0] = v
            with self.subTest(fsr=fsr):
                self.assertAlmostEqual(self.adc.read_voltage(0), v, delta=self.lsb(fsr))

    def test_read_raw_counts(self):
        self.chip.volts[0] = 2.048
        self.assertEqual(self.adc.read_raw(0), 16384)
        self.chip.volts[0] = 0.0
        self.assertEqual(self.adc.read_raw(0), 0)

    def test_negative_codes_are_sign_extended(self):
        self.chip.volts[0] = -0.001   # e.g. offset just below GND
        raw = self.adc.read_raw(0)
        self.assertLess(raw, 0)
        self.assertEqual(raw, -8)

    def test_full_scale_clips(self):
        self.chip.volts[0] = 5.0
        self.assertEqual(self.adc.read_raw(0), 32767)
        self.assertAlmostEqual(self.adc.read_voltage(0), 4.096, delta=self.lsb())
        self.chip.volts[0] = -5.0
        self.assertEqual(self.adc.read_raw(0), -32768)

    def test_averaging(self):
        self.assertAlmostEqual(self.adc.read_voltage(1, samples=16), 1.65, delta=self.lsb())
        self.assertEqual(self.chip.conversions, 16)

    def test_single_sample_by_default(self):
        self.adc.read_voltage(0)
        self.assertEqual(self.chip.conversions, 1)

    def test_differential(self):
        cases = {(0, 1): -0.65, (0, 3): -2.0, (1, 3): -1.35, (2, 3): -2.8}
        for (pos, neg), expected in cases.items():
            with self.subTest(pair=(pos, neg)):
                self.assertAlmostEqual(self.adc.read_differential(pos, neg), expected, delta=self.lsb())

    def test_differential_positive(self):
        self.chip.volts = [2.0, 0.5, 0.0, 0.0]
        self.assertAlmostEqual(self.adc.read_differential(0, 1), 1.5, delta=self.lsb())

    def test_unsupported_differential_pair(self):
        for pair in ((1, 0), (1, 2), (0, 2), (3, 2)):
            with self.subTest(pair=pair), self.assertRaises(KeyError):
                self.adc.read_differential(*pair)

    def test_invalid_channel(self):
        with self.assertRaises(IndexError):
            self.adc.read_raw(4)

    def test_missing_board_raises_oserror(self):
        adc = self.mod.ADS1115(self.bus, address=0x49)
        with self.assertRaises(OSError):
            adc.read_voltage(0)

    def test_settings_can_change_between_reads(self):
        self.chip.volts[0] = 1.0
        self.adc.fsr = 1.024
        self.adc.rate = 8
        self.assertAlmostEqual(self.adc.read_voltage(0), 1.0, delta=self.lsb(1.024))
        self.assertEqual(self.last_config() & (PGA_MASK | DR_MASK), PGA[1.024] | DR[8])


class TestConversionWait(_DriverTestCase):
    chip_kwargs = {"busy_polls": 3}

    def test_waits_one_conversion_period_first(self):
        for rate in (8, 128, 860):
            self.time.slept_us.clear()
            self.adc.rate = rate
            self.adc.read_raw(0)
            with self.subTest(rate=rate):
                self.assertGreaterEqual(self.time.slept_us[0], 1_000_000 / rate)

    def test_polls_until_conversion_done(self):
        self.adc.read_raw(0)
        self.assertEqual(self.chip.config_reads, 4)   # three busy reads, then done

    def test_gives_up_after_100_polls(self):
        chip = fakes.ADS1115Chip([1.0] * 4, never_ready=True)
        adc = self.mod.ADS1115(fakes.FakeI2C({0x48: chip}))
        self.assertAlmostEqual(adc.read_voltage(0), 1.0, delta=self.lsb())
        self.assertEqual(chip.config_reads, 100)


class TestReadyPin(_DriverTestCase):
    def test_enable_sets_thresholds_for_ready_mode(self):
        self.adc.enable_ready_pin()
        self.assertIn((REG_HI_THRESH, 0x8000), self.chip.writes)
        self.assertIn((REG_LO_THRESH, 0x0000), self.chip.writes)

    def test_comparator_on_after_enable(self):
        self.adc.enable_ready_pin()
        self.adc.read_raw(0)
        self.assertEqual(self.last_config() & 0x3, 0x0)   # assert after one conversion
        self.assertTrue(self.chip.rdy_enabled())

    def test_ready_pulses_once_per_conversion(self):
        pulses = []
        self.chip.on_ready = lambda: pulses.append(1)
        self.adc.read_raw(0)
        self.assertEqual(pulses, [])        # RDY stays idle until enabled
        self.adc.enable_ready_pin()
        for ch in range(4):
            self.adc.start(ch)
        self.assertEqual(len(pulses), 4)

    def test_start_returns_without_waiting(self):
        self.adc.start(1)
        self.assertEqual(self.chip.conversions, 1)
        self.assertEqual(self.chip.config_reads, 0)
        self.assertEqual(self.time.slept_us, [])
        self.assertEqual(len(self.chip.config_writes()), 1)
        self.assertEqual(self.last_config() & MUX_MASK, MUX_SINGLE[1])

    def test_result_voltage(self):
        self.adc.start(1)
        self.assertAlmostEqual(self.adc.result_voltage(), 1.65, delta=self.lsb())
        self.chip.volts[3] = -0.002
        self.adc.start(3)
        self.assertLess(self.adc.result_voltage(), 0)

    def test_result_voltage_uses_current_range(self):
        self.adc.fsr = 2.048
        self.adc.start(0)
        self.assertAlmostEqual(self.adc.result_voltage(), 1.0, delta=self.lsb(2.048))


if __name__ == "__main__":
    unittest.main()
