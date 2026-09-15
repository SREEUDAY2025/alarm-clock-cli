import contextlib
import io
import unittest
from unittest.mock import patch

from alarmclock.cli import build_parser, guided_setup, main


class TerminalOutput(io.StringIO):
    def isatty(self):
        return True


class SetupTests(unittest.TestCase):
    def setup_with(self, answers):
        output = io.StringIO()
        with patch("builtins.input", side_effect=answers), contextlib.redirect_stdout(output):
            arguments = guided_setup()
        return build_parser().parse_args(arguments), output.getvalue()

    def test_defaults_create_ten_minute_timer(self):
        args, output = self.setup_with(["", "", "", "", "", ""])
        self.assertEqual(args.duration, "10m")
        self.assertEqual(args.label, "Alarm")
        self.assertFalse(args.quiet)
        self.assertEqual(args.ring_seconds, 10)

    def test_scheduled_alarm_recovers_from_invalid_time(self):
        args, output = self.setup_with(["2", "25:00", "07:30", "Wake up", "n", "1", "y"])
        self.assertEqual(args.at, "07:30")
        self.assertEqual(args.label, "Wake up")
        self.assertTrue(args.quiet)
        self.assertIn("Please try again", output)
        self.assertIn("tomorrow", output)

    def test_invalid_fields_retry_without_losing_previous_answers(self):
        answers = ["1", "0s", "5s", "\x1b[2J", "Tea", "maybe", "n", "0", "2", "y"]
        args, output = self.setup_with(answers)
        self.assertEqual(args.duration, "5s")
        self.assertEqual(args.label, "Tea")
        self.assertTrue(args.quiet)
        self.assertEqual(args.ring_seconds, 2)
        self.assertEqual(output.count("Please try again"), 4)

    def test_demo_and_invalid_menu_choice(self):
        args, output = self.setup_with(["wrong", "3"])
        self.assertEqual(args.duration, "5s")
        self.assertEqual(args.label, "Demo alarm")
        self.assertEqual(args.ring_seconds, 2)
        self.assertIn("Please try again", output)

    def invoke_terminal(self, answers):
        output = TerminalOutput()
        with contextlib.redirect_stdout(output), patch("sys.stdin.isatty", return_value=True):
            with patch("builtins.input", side_effect=answers), patch("alarmclock.cli.run") as run, patch("alarmclock.cli.supports_dashboard", return_value=False):
                status = main([])
        return status, output.getvalue(), run

    def test_declining_confirmation_does_not_start_alarm(self):
        status, output, run = self.invoke_terminal(["1", "5s", "Tea", "n", "2", "n"])
        self.assertEqual(status, 0)
        run.assert_not_called()
        self.assertIn("No alarm was started", output)

    def test_quit_during_setup_does_not_start_alarm(self):
        status, output, run = self.invoke_terminal(["1", "q"])
        self.assertEqual(status, 0)
        run.assert_not_called()

    def test_end_of_input_cancels_cleanly(self):
        status, output, run = self.invoke_terminal(EOFError)
        self.assertEqual(status, 0)
        run.assert_not_called()
        self.assertIn("Setup cancelled", output)

    def test_ctrl_c_cancels_setup(self):
        status, output, run = self.invoke_terminal(KeyboardInterrupt)
        self.assertEqual(status, 130)
        run.assert_not_called()
        self.assertIn("Setup cancelled", output)

    def test_redirected_input_never_prompts(self):
        with patch("sys.stdin.isatty", return_value=False), patch("builtins.input") as read:
            with contextlib.redirect_stdout(TerminalOutput()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    main([])
        self.assertEqual(result.exception.code, 2)
        read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
