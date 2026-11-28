"""Unit tests for python/pingoblin_ads1115/ads1115.py (the Raspberry Pi driver), against a
register-level ADS1115 model on a fake smbus2 bus."""
import sys
import threading
import unittest
from unittest import mock

import fakes
from fakes import DR, DR_MASK, MODE_SINGLE, MUX_DIFF, MUX_MASK, MUX_SINGLE, OS, PGA, PGA_MASK, QUE_MASK

pkg, drv = fakes.load_pi_driver()


class _PiTestCase(unittest.TestCase):
    volts = (1.0, 1.65, 0.2, 3.0)
    chip_kwargs = {}

    def setUp(self):
        self.chip = fakes.ADS1115Chip(self.volts, **self.chip_kwargs)
        self.chips = {0x48: self.chip}
        self.smbus2 = fakes.make_smbus2(self.chips)
        self.sleep = fakes.FakeSleep()
        for patcher in (mock.patch.dict(sys.modules, {"smbus2": self.smbus2}),
                        mock.patch.object(drv, "time", self.sleep)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.adc = pkg.ADS1115()

    def last_config(self, chip=None):
        return (chip or self.chip).config_writes()[-1]

    def lsb(self, fsr=None):
        return (fsr or self.adc.fsr) / 32768


class TestConstructor(_PiTestCase):
    def test_defaults(self):
        self.assertEqual((self.adc.address, self.adc.fsr, self.adc.rate), (0x48, 4.096, 128))

    def test_bus_number_opens_smbus(self):
        adc = pkg.ADS1115(bus=3)
        self.assertEqual(self.smbus2.opened[-1].bus, 3)
        adc.close()
        self.assertTrue(self.smbus2.opened[-1].closed)

    def test_bus_object_is_used_and_not_closed(self):
        bus = self.smbus2.SMBus(1)
        opened = len(self.smbus2.opened)
        with pkg.ADS1115(bus) as adc:
            self.assertAlmostEqual(adc.read_voltage(0), 1.0, delta=self.lsb())
        self.assertEqual(len(self.smbus2.opened), opened)
        self.assertFalse(bus.closed)

    def test_context_manager_closes_own_bus(self):
        with pkg.ADS1115() as adc:
            adc.read_raw(0)
        self.assertTrue(self.smbus2.opened[-1].closed)

    def test_no_bus_traffic_on_construction(self):
        self.assertEqual(self.chip.writes, [])

    def test_every_valid_setting(self):
        for address in pkg.ADDRESSES:
            for fsr in PGA:
                for rate in DR:
                    with self.subTest(address=address, fsr=fsr, rate=rate):
                        adc = pkg.ADS1115(address=address, fsr=fsr, rate=rate)
                        self.assertEqual((adc.address, adc.fsr, adc.rate), (address, fsr, rate))

    def test_invalid_settings(self):
        for kwargs, word in ((dict(address=0x50), "address"), (dict(address=0x47), "address"),
                             (dict(fsr=5.0), "fsr"), (dict(fsr=3.3), "fsr"),
                             (dict(rate=100), "rate"), (dict(rate=0), "rate")):
            with self.subTest(**kwargs), self.assertRaisesRegex(ValueError, word):
                pkg.ADS1115(**kwargs)

    def test_invalid_settings_do_not_open_bus(self):
        with self.assertRaises(ValueError):
            pkg.ADS1115(fsr=5.0)
        self.assertEqual(len(self.smbus2.opened), 1)    # only the one from setUp


class TestConfigWord(_PiTestCase):
    def test_default_read(self):
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

    def test_gain_and_rate_bits(self):
        for fsr, pga in PGA.items():
            for rate, dr in DR.items():
                self.adc.fsr, self.adc.rate = fsr, rate
                self.adc.read_raw(0)
                with self.subTest(fsr=fsr, rate=rate):
                    self.assertEqual(self.last_config() & (PGA_MASK | DR_MASK), pga | dr)

    def test_every_conversion_is_single_shot_with_start_bit_and_comparator_off(self):
        self.adc.read_raw(0)
        self.adc.read_voltage(1, samples=3)
        self.adc.read_differential(0, 1)
        for cfg in self.chip.config_writes():
            self.assertTrue(cfg & OS)
            self.assertTrue(cfg & MODE_SINGLE)
            self.assertEqual(cfg & QUE_MASK, 0x3)


class TestReads(_PiTestCase):
    def test_each_channel(self):
        for ch, v in enumerate(self.volts):
            with self.subTest(ch=ch):
                self.assertAlmostEqual(self.adc.read_voltage(ch), v, delta=self.lsb())

    def test_every_range(self):
        for fsr in PGA:
            self.adc.fsr = fsr
            self.chip.volts[0] = fsr * 0.6
            with self.subTest(fsr=fsr):
                self.assertAlmostEqual(self.adc.read_voltage(0), fsr * 0.6, delta=self.lsb(fsr))

    def test_raw_counts_and_sign(self):
        self.chip.volts[0] = 2.048
        self.assertEqual(self.adc.read_raw(0), 16384)
        self.chip.volts[0] = -0.001
        self.assertEqual(self.adc.read_raw(0), -8)

    def test_full_scale_codes(self):
        self.chip.volts[0] = 5.0
        self.assertEqual(self.adc.read_raw(0), 32767)
        self.chip.volts[0] = -5.0
        self.assertEqual(self.adc.read_raw(0), -32768)

    def test_averaging(self):
        self.assertAlmostEqual(self.adc.read_voltage(1, samples=16), 1.65, delta=self.lsb())
        self.assertEqual(self.chip.conversions, 16)

    def test_differential(self):
        for (pos, neg), expected in {(0, 1): -0.65, (0, 3): -2.0, (1, 3): -1.35, (2, 3): -2.8}.items():
            with self.subTest(pair=(pos, neg)):
                self.assertAlmostEqual(self.adc.read_differential(pos, neg), expected, delta=self.lsb())
        self.assertAlmostEqual(self.adc.read_differential(0, 1, samples=4), -0.65, delta=self.lsb())

    def test_invalid_channel(self):
        for call in (lambda: self.adc.read_raw(4), lambda: self.adc.read_voltage(-1),
                     lambda: self.adc.read_voltage(4, samples=2)):
            with self.assertRaisesRegex(ValueError, "channel"):
                call()
        self.assertEqual(self.chip.writes, [])

    def test_unsupported_pair(self):
        for pair in ((1, 0), (1, 2), (0, 2), (3, 2)):
            with self.subTest(pair=pair), self.assertRaisesRegex(ValueError, "pair"):
                self.adc.read_differential(*pair)

    def test_address_is_used(self):
        other = fakes.ADS1115Chip([0.5] * 4)
        self.chips[0x4B] = other
        self.assertAlmostEqual(pkg.ADS1115(address=0x4B).read_voltage(0), 0.5, delta=self.lsb())
        self.assertEqual((other.conversions, self.chip.conversions), (1, 0))


class TestConversionWait(_PiTestCase):
    chip_kwargs = {"busy_polls": 3}

    def test_waits_one_conversion_period_first(self):
        for rate in (8, 128, 860):
            self.sleep.calls.clear()
            self.adc.rate = rate
            self.adc.read_raw(0)
            with self.subTest(rate=rate):
                self.assertGreaterEqual(self.sleep.calls[0], 1 / rate)

    def test_polls_until_done(self):
        self.adc.read_raw(0)
        self.assertEqual(self.chip.config_reads, 4)

    def test_gives_up_after_100_polls(self):
        self.chip.never_ready = True
        self.assertAlmostEqual(self.adc.read_voltage(0), 1.0, delta=self.lsb())
        self.assertEqual(self.chip.config_reads, 100)


class TestInputRange(_PiTestCase):
    """A reading at full scale raises InputRangeError; the next valid reading works."""

    def test_full_scale_raises_with_a_fix_in_the_message(self):
        self.chip.volts[2] = 5.0
        with self.assertRaises(pkg.InputRangeError) as cm:
            self.adc.read_voltage(2, samples=3)
        self.assertIsInstance(cm.exception, ValueError)
        message = str(cm.exception)
        self.assertIn("CH2", message)
        self.assertIn("±4.096 V", message)
        self.assertIn("ADS1115(fsr=6.144) on a board powered from 5 V", message)

    def test_next_read_works_once_the_cause_has_gone(self):
        self.chip.volts[2] = 5.0
        with self.assertRaises(pkg.InputRangeError):
            self.adc.read_voltage(2)
        self.chip.volts[2] = 2.0
        self.assertAlmostEqual(self.adc.read_voltage(2), 2.0, delta=self.lsb())

    def test_one_full_scale_sample_spoils_the_average(self):
        values = iter([3.0, 5.0, 3.0])
        original = self.chip._convert

        def convert(config):
            self.chip.volts[0] = next(values)
            original(config)
        self.chip._convert = convert
        with self.assertRaises(pkg.InputRangeError):
            self.adc.read_voltage(0, samples=3)

    def test_negative_full_scale_and_differential(self):
        adc = pkg.ADS1115(fsr=2.048)
        with self.assertRaises(pkg.InputRangeError) as cm:
            adc.read_differential(2, 3)              # 0.2 − 3.0 = −2.8 V, below −2.048 V
        self.assertIn("CH2−CH3", str(cm.exception))
        self.assertIn("fsr=4.096", str(cm.exception))

    def test_largest_range_message(self):
        self.adc.fsr = 6.144
        self.chip.volts[0] = 7.0
        with self.assertRaisesRegex(pkg.InputRangeError, "Keep every input between 0 V and VDD"):
            self.adc.read_voltage(0)

    def test_read_raw_returns_the_full_scale_code(self):
        self.chip.volts[3] = 4.2
        self.assertEqual(self.adc.read_raw(3), 32767)

    def test_just_inside_range(self):
        self.chip.volts[0] = 4.0
        self.assertAlmostEqual(self.adc.read_voltage(0), 4.0, delta=self.lsb())

    def test_larger_range_fixes_it(self):
        self.chip.volts[0] = 4.5                     # a 5 V board in RES mode
        with self.assertRaises(pkg.InputRangeError):
            self.adc.read_voltage(0)
        self.adc.fsr = 6.144
        self.assertAlmostEqual(self.adc.read_voltage(0), 4.5, delta=self.lsb(6.144))

    def test_result_voltage_names_the_started_channel(self):
        self.chip.volts[1] = 5.0
        self.adc.start(1)
        with self.assertRaisesRegex(pkg.InputRangeError, "CH1"):
            self.adc.result_voltage()
        self.chip.volts[1] = 1.0
        self.adc.start(1)
        self.assertAlmostEqual(self.adc.result_voltage(), 1.0, delta=self.lsb())


class TestBusError(_PiTestCase):
    def test_missing_board(self):
        adc = pkg.ADS1115(address=0x49)
        for call in (lambda: adc.read_voltage(0), lambda: adc.read_raw(1), lambda: adc.start(0),
                     lambda: adc.result_voltage(), adc.enable_ready_pin):
            with self.assertRaises(pkg.BusError) as cm:
                call()
            self.assertIsInstance(cm.exception, OSError)      # existing `except OSError` still works
            self.assertIn("0x49", str(cm.exception))
            self.assertIn("Check the J1 wiring, the power and the address jumpers", str(cm.exception))
            self.assertIsInstance(cm.exception.__cause__, OSError)

    def test_next_read_works_once_the_board_answers(self):
        adc = pkg.ADS1115(address=0x49)
        with self.assertRaises(pkg.BusError):
            adc.read_voltage(0)
        self.chips[0x49] = fakes.ADS1115Chip([0.7] * 4)
        self.assertAlmostEqual(adc.read_voltage(0), 0.7, delta=self.lsb())


class TestReadyPin(_PiTestCase):
    def test_enable_sets_ready_mode(self):
        pulses = []
        self.chip.on_ready = lambda: pulses.append(1)
        self.adc.read_raw(0)
        self.assertEqual(pulses, [])
        self.adc.enable_ready_pin()
        self.assertIn((fakes.REG_HI_THRESH, 0x8000), self.chip.writes)
        self.assertIn((fakes.REG_LO_THRESH, 0x0000), self.chip.writes)
        for ch in range(4):
            self.adc.start(ch)
        self.assertEqual(len(pulses), 4)
        self.assertEqual(self.last_config() & QUE_MASK, 0)

    def test_start_checks_the_channel(self):
        with self.assertRaisesRegex(ValueError, "channel"):
            self.adc.start(4)

    def test_start_returns_without_waiting(self):
        self.adc.start(2)
        self.assertEqual((self.chip.conversions, self.chip.config_reads, self.sleep.calls), (1, 0, []))
        self.assertEqual(self.last_config() & MUX_MASK, MUX_SINGLE[2])

    def test_result_voltage(self):
        self.adc.start(1)
        self.assertAlmostEqual(self.adc.result_voltage(), 1.65, delta=self.lsb())
        self.chip.volts[3] = -0.002
        self.adc.start(3)
        self.assertLess(self.adc.result_voltage(), 0)


class TestThreadSafety(_PiTestCase):
    def test_concurrent_readers_get_their_own_channel(self):
        errors = []
        interval = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)                  # switch threads as often as possible
        self.addCleanup(sys.setswitchinterval, interval)

        def reader(ch):
            for _ in range(300):
                if abs(self.adc.read_voltage(ch) - self.volts[ch]) > self.lsb():
                    errors.append(ch)
        threads = [threading.Thread(target=reader, args=(ch,)) for ch in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(self.chip.conversions, 1200)


class TestMockBus(unittest.TestCase):
    """The simulated bus that every example uses with --mock."""

    def setUp(self):
        patcher = mock.patch.object(drv, "time", fakes.FakeSleep())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_default_board(self):
        bus = pkg.MockBus()
        adc = pkg.ADS1115(bus)
        for ch, v in enumerate(pkg.DEFAULT_VOLTS):
            self.assertAlmostEqual(adc.read_voltage(ch), v, delta=4.096 / 32768)
        self.assertEqual(pkg.DEFAULT_VOLTS, (1.65, 1.65, 2.5, 3.0))
        self.assertEqual(adc.read_raw(0), 13200)

    def test_needs_no_smbus2(self):
        with mock.patch.dict(sys.modules, {"smbus2": None}):
            self.assertAlmostEqual(pkg.ADS1115(pkg.MockBus()).read_voltage(3), 3.0, delta=0.001)

    def test_change_voltages_ranges_and_differential(self):
        bus = pkg.MockBus(volts=(0.1, 0.2, 0.3, 0.4), addresses=(0x48, 0x4B))
        bus.volts[0x4B][2] = 0.75
        adc = pkg.ADS1115(bus, address=0x4B, fsr=1.024)
        self.assertAlmostEqual(adc.read_voltage(2), 0.75, delta=1.024 / 32768)
        self.assertAlmostEqual(adc.read_differential(0, 1), -0.1, delta=1.024 / 32768)
        bus.volts[0x4B][2] = 2.0
        with self.assertRaises(pkg.InputRangeError):
            adc.read_voltage(2)
        self.assertAlmostEqual(pkg.ADS1115(bus).read_voltage(2), 0.3, delta=4.096 / 32768)

    def test_missing_address_and_find_boards(self):
        bus = pkg.MockBus(addresses=(0x48, 0x49))
        with self.assertRaises(pkg.BusError):
            pkg.ADS1115(bus, address=0x4A).read_voltage(0)
        self.assertEqual(list(pkg.find_boards(bus)), [0x48, 0x49])
        bus.close()                                  # nothing to close

    def test_ready_mode(self):
        adc = pkg.ADS1115(pkg.MockBus())
        adc.enable_ready_pin()
        adc.start(2)
        self.assertAlmostEqual(adc.result_voltage(), 2.5, delta=4.096 / 32768)


class TestFindBoards(_PiTestCase):
    def test_finds_every_board_on_one_bus(self):
        self.chips[0x4A] = fakes.ADS1115Chip([0.5] * 4)
        boards = pkg.find_boards(fsr=2.048, rate=860)
        self.assertEqual(list(boards), [0x48, 0x4A])
        self.assertIs(boards[0x48]._bus, boards[0x4A]._bus)
        self.assertEqual({(b.fsr, b.rate) for b in boards.values()}, {(2.048, 860)})
        self.assertAlmostEqual(boards[0x4A].read_voltage(0), 0.5, delta=self.lsb(2.048))

    def test_none(self):
        self.chips.clear()
        self.assertEqual(pkg.find_boards(), {})

    def test_address_subset_and_bus_object(self):
        self.chips[0x49] = fakes.ADS1115Chip([0.5] * 4)
        bus = self.smbus2.SMBus(1)
        boards = pkg.find_boards(bus, addresses=(0x49,))
        self.assertEqual(list(boards), [0x49])
        self.assertIs(boards[0x49]._bus, bus)


if __name__ == "__main__":
    unittest.main()
