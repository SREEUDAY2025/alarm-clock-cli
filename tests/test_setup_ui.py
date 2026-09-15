import contextlib
import io
import unittest
from unittest.mock import patch

from alarmclock.cli import build_parser, main
from alarmclock.core import parse_duration
from alarmclock.setup_ui import choose, edit, setup


class SetupScreenTests(unittest.TestCase):
    def invoke(self, keys):
        with patch('alarmclock.setup_ui.terminal_screen', contextlib.nullcontext), patch('alarmclock.setup_ui.read_key', side_effect=keys), patch('alarmclock.setup_ui.paint'):
            args = setup()
        return build_parser().parse_args(args) if args is not None else None

    def test_preset_starts_without_optional_questions(self):
        args = self.invoke(['enter', '2', 'enter'])
        self.assertEqual(args.duration, '10m')
        self.assertEqual(args.label, 'Alarm')
        self.assertFalse(args.quiet)
        self.assertEqual(args.ring_seconds, 10)

    def test_custom_duration_and_optional_settings(self):
        args = self.invoke(['1', '4', '3', '0', 's', 'enter', '2', '1', 'T', 'e', 'a', 'enter', '2', '3', '2', 'enter', '4', '1'])
        self.assertEqual(args.duration, '30s')
        self.assertEqual(args.label, 'Tea')
        self.assertTrue(args.quiet)
        self.assertEqual(args.ring_seconds, 2)

    def test_local_alarm(self):
        args = self.invoke(['2', 'enter', 'enter'])
        self.assertEqual(args.at, '07:30')

    def test_quick_demo(self):
        args = self.invoke(['3'])
        self.assertEqual(args.duration, '5s')
        self.assertEqual(args.ring_seconds, 2)

    def test_back_and_quit_do_not_create_alarm(self):
        self.assertIsNone(self.invoke(['1', 'escape', '4']))

    def test_arrow_keys_select_and_wrap(self):
        with patch('alarmclock.setup_ui.paint'), patch('alarmclock.setup_ui.read_key', side_effect=['up', 'enter']):
            self.assertEqual(choose('Test', ['First', 'Second', 'Last']), 2)

    def test_invalid_edit_stays_visible_and_can_be_corrected(self):
        with patch('alarmclock.setup_ui.paint') as paint, patch('alarmclock.setup_ui.read_key', side_effect=['0', 's', 'enter', 'backspace', 'backspace', '5', 's', 'enter']):
            self.assertEqual(edit('Duration', 'Example: 5s', '10m', parse_duration), '5s')
        self.assertTrue(any('between 1 second' in str(call) for call in paint.call_args_list))

    def test_interactive_main_uses_screen_and_shared_parser(self):
        with patch('sys.stdin.isatty', return_value=True), patch('sys.stdout.isatty', return_value=True), patch('alarmclock.cli.supports_dashboard', return_value=True), patch('alarmclock.setup_ui.setup', return_value=['--in', '5s']), patch('alarmclock.cli.run', return_value=0) as run:
            self.assertEqual(main([]), 0)
        self.assertEqual(run.call_args.args[0].duration, '5s')

    def test_interruption_exits_screen_context(self):
        events = []
        @contextlib.contextmanager
        def screen():
            try:
                yield
            finally:
                events.append('restored')
        with patch('alarmclock.setup_ui.terminal_screen', screen), patch('alarmclock.setup_ui.paint'), patch('alarmclock.setup_ui.read_key', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                setup()
        self.assertEqual(events, ['restored'])
