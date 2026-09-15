import unittest
from datetime import datetime

from alarmclock.core import next_occurrence, parse_duration, wait_until


class ParsingTests(unittest.TestCase):
    def test_durations(self):
        for text, expected in [("1s", 1), ("10m", 600), ("1h30m5s", 5405), ("90m", 5400), ("168h", 604800)]:
            with self.subTest(text=text):
                self.assertEqual(parse_duration(text), expected)

    def test_reject_invalid_durations(self):
        for text in ["", "0s", "-1s", "1.5m", "10", "1m1h", "1s1s", "1H", " 1s", "1s\n", "169h", "9999999999h", "１s"]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_duration(text)

    def test_future_time_today(self):
        now = datetime(2026, 9, 15, 6, 0)
        self.assertEqual(next_occurrence("07:30", now), datetime(2026, 9, 15, 7, 30))

    def test_optional_seconds(self):
        now = datetime(2026, 9, 15, 6, 0)
        self.assertEqual(next_occurrence("06:00:01", now), datetime(2026, 9, 15, 6, 0, 1))

    def test_equal_time_means_tomorrow(self):
        now = datetime(2026, 9, 15, 7, 30)
        self.assertEqual(next_occurrence("07:30", now), datetime(2026, 9, 16, 7, 30))

    def test_past_time_and_year_rollover(self):
        now = datetime(2026, 12, 31, 23, 59, 59)
        self.assertEqual(next_occurrence("00:00", now), datetime(2027, 1, 1))

    def test_reject_invalid_times(self):
        for text in ["7:30", "24:00", "12:60", "12:30:60", "-1:00", "noon", "12:30\n"]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    next_occurrence(text, datetime(2026, 9, 15))


class FakeClock:
    def __init__(self, now=0):
        self.now = now
        self.sleeps = []

    def read(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class WaitingTests(unittest.TestCase):
    def test_bounded_sleep_and_exact_deadline(self):
        clock = FakeClock()
        ticks = []
        wait_until(2.5, clock=clock.read, sleep=clock.sleep, on_tick=ticks.append)
        self.assertEqual(clock.sleeps, [1, 1, 0.5])
        self.assertEqual(ticks, [2.5, 1.5, 0.5])
        self.assertEqual(clock.now, 2.5)

    def test_already_due_does_not_sleep(self):
        clock = FakeClock(10)
        wait_until(9, clock=clock.read, sleep=clock.sleep)
        self.assertEqual(clock.sleeps, [])

    def test_forward_clock_jump_fires_on_next_check(self):
        clock = FakeClock()

        def jump(seconds):
            clock.sleep(seconds)
            clock.now += 100

        wait_until(10, clock=clock.read, sleep=jump)
        self.assertEqual(clock.sleeps, [1])

    def test_backward_clock_jump_waits_until_due(self):
        clock = FakeClock()

        def jump_once(seconds):
            clock.sleep(seconds)
            if len(clock.sleeps) == 1:
                clock.now -= 2

        wait_until(2, clock=clock.read, sleep=jump_once)
        self.assertEqual(clock.now, 2)
        self.assertEqual(clock.sleeps, [1, 1, 1, 1])

    def test_early_sleep_return_rechecks_clock(self):
        clock = FakeClock()

        def interrupted_sleep(seconds):
            clock.sleep(min(seconds, 0.25))

        wait_until(1, clock=clock.read, sleep=interrupted_sleep)
        self.assertEqual(clock.now, 1)
        self.assertEqual(len(clock.sleeps), 4)
