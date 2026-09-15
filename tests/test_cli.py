import contextlib
import io
import unittest
from unittest.mock import patch

from alarmclock.cli import countdown, main


class CliTests(unittest.TestCase):
    def invoke(self, argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(argv)
        return status, output.getvalue()

    def test_help(self):
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as result:
            main(["--help"])
        self.assertEqual(result.exception.code, 0)

    def test_invalid_arguments(self):
        for argv in [[], ["--in", "1s", "--at", "07:30"], ["--in", "0s"], ["--at", "25:00"],
                     ["--in", "1s", "--ring-seconds", "0"], ["--in", "1s", "--ring-seconds", "61"],
                     ["--in", "1s", "--ring-seconds", "abc"], ["--in", "1s", "--label", "\x1b[2J"]]:
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), patch("sys.stdin.isatty", return_value=False):
                with self.assertRaises(SystemExit) as result:
                    main(argv)
                self.assertEqual(result.exception.code, 2)

    @patch("alarmclock.cli.time.sleep")
    @patch("alarmclock.cli.wait_until")
    def test_timer_uses_monotonic_clock(self, wait, sleep):
        with patch("alarmclock.cli.time.monotonic", return_value=100) as monotonic:
            status, output = self.invoke(["--in", "2s", "--label", "Tea", "--ring-seconds", "1"])
            self.assertEqual(wait.call_args.args, (102,))
            self.assertIs(wait.call_args.kwargs["clock"], monotonic)
        self.assertEqual(status, 0)
        self.assertIn("ALARM! Tea", output)
        self.assertEqual(output.count("\a"), 1)
        sleep.assert_called_once_with(1)

    @patch("alarmclock.cli.time.sleep")
    @patch("alarmclock.cli.wait_until")
    def test_at_uses_wall_clock(self, wait, sleep):
        with patch("alarmclock.cli.time.time") as wall_clock:
            status, output = self.invoke(["--at", "07:30", "--quiet", "--ring-seconds", "1"])
            self.assertIs(wait.call_args.kwargs["clock"], wall_clock)
        self.assertEqual(status, 0)
        self.assertIn("ALARM!", output)
        self.assertNotIn("\a", output)
        self.assertNotIn("Time remaining", output)

    @patch("alarmclock.cli.wait_until", side_effect=KeyboardInterrupt)
    def test_cancel_wait(self, wait):
        status, output = self.invoke(["--in", "1h"])
        self.assertEqual(status, 130)
        self.assertIn("Alarm stopped.", output)
        self.assertNotIn("ALARM!", output)

    @patch("alarmclock.cli.time.sleep", side_effect=KeyboardInterrupt)
    @patch("alarmclock.cli.wait_until")
    def test_cancel_ringing(self, wait, sleep):
        status, output = self.invoke(["--in", "1s"])
        self.assertEqual(status, 130)
        self.assertIn("ALARM!", output)
        self.assertIn("Alarm stopped.", output)

    @patch("alarmclock.cli.time.sleep")
    @patch("alarmclock.cli.wait_until")
    def test_default_alert_repeats_ten_times(self, wait, sleep):
        status, output = self.invoke(["--in", "1s"])
        self.assertEqual(status, 0)
        self.assertEqual(output.count("\a"), 10)
        self.assertEqual(sleep.call_count, 10)

    def test_countdown_rounds_up_instead_of_showing_zero_early(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            countdown(0.1)
            countdown(3661)
        self.assertIn("00:00:01", output.getvalue())
        self.assertIn("01:01:01", output.getvalue())


if __name__ == "__main__":
    unittest.main()
