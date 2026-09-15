import contextlib
from datetime import datetime
import io
import os
import unittest
from unittest.mock import patch

from alarmclock.cli import main
from alarmclock.display import Dashboard, clock_text, supports_dashboard


class TerminalOutput(io.StringIO):
    def isatty(self):
        return True


class DisplayTests(unittest.TestCase):
    def test_countdown_handles_partial_seconds_and_long_timers(self):
        self.assertEqual(clock_text(0.1), "00:00:01")
        self.assertEqual(clock_text(-1), "00:00:00")
        self.assertEqual(clock_text(604800), "168:00:00")

    def test_redirected_output_never_uses_dashboard(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(supports_dashboard())

    def test_no_color_and_dumb_terminal_disable_dashboard(self):
        for environment in [{"NO_COLOR": ""}, {"TERM": "dumb"}]:
            with self.subTest(environment=environment):
                with contextlib.redirect_stdout(TerminalOutput()), patch.dict(os.environ, environment):
                    self.assertFalse(supports_dashboard())

    def test_small_terminal_keeps_a_readable_status(self):
        output = TerminalOutput()
        dashboard = Dashboard("Tea", datetime(2026, 9, 15, 7, 30), 10, True)
        with contextlib.redirect_stdout(output):
            with patch("alarmclock.display.shutil.get_terminal_size", return_value=os.terminal_size((30, 10))):
                dashboard.draw(5)
        self.assertIn("00:00:05", output.getvalue())
        self.assertIn("Ctrl+C to stop", output.getvalue())
        self.assertNotIn("╭", output.getvalue())

    @patch("alarmclock.cli.supports_dashboard", return_value=True)
    @patch("alarmclock.cli.wait_until", side_effect=KeyboardInterrupt)
    def test_interruption_restores_cursor_and_original_screen(self, wait, support):
        output = TerminalOutput()
        with contextlib.redirect_stdout(output):
            result = main(["--in", "1h"])
        self.assertEqual(result, 130)
        self.assertIn("\033[?1049h\033[?25l", output.getvalue())
        self.assertIn("\033[?25h\033[?1049l", output.getvalue())
        self.assertIn("Alarm stopped.", output.getvalue())

    @patch("alarmclock.cli.time.sleep")
    @patch("alarmclock.cli.wait_until")
    @patch("alarmclock.cli.supports_dashboard", return_value=True)
    def test_finished_dashboard_restores_screen_and_retains_summary(self, support, wait, sleep):
        output = TerminalOutput()
        with contextlib.redirect_stdout(output):
            result = main(["--in", "1s", "--quiet", "--ring-seconds", "1"])
        self.assertEqual(result, 0)
        self.assertIn("Alarm ringing", output.getvalue())
        restored = output.getvalue().split("\033[?1049l")[-1]
        self.assertIn("ALARM! Alarm", restored)
        self.assertIn("Alarm finished.", restored)
        self.assertNotIn("\a", output.getvalue())

    @patch("alarmclock.cli.time.sleep")
    @patch("alarmclock.cli.wait_until")
    def test_plain_flag_disables_control_sequences(self, wait, sleep):
        output = TerminalOutput()
        with contextlib.redirect_stdout(output):
            main(["--in", "1s", "--plain", "--quiet", "--ring-seconds", "1"])
        self.assertNotIn("\033", output.getvalue())


if __name__ == "__main__":
    unittest.main()
