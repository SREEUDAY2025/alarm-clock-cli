"""Exercise the actual module entry point and OS process behavior."""

import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProcessTests(unittest.TestCase):
    def test_real_alarm_fires_after_delay_and_finishes(self):
        start = time.monotonic()
        result = subprocess.run(
            [sys.executable, "-m", "alarmclock", "--in", "1s", "--quiet",
             "--ring-seconds", "1", "--label", "Integration test"],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(time.monotonic() - start, 2)
        self.assertIn("ALARM! Integration test", result.stdout)
        self.assertIn("Alarm finished.", result.stdout)
        self.assertNotIn("\a", result.stdout)
        self.assertNotIn("\r", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_invalid_input_has_helpful_error_without_traceback(self):
        result = subprocess.run(
            [sys.executable, "-m", "alarmclock", "--in", "0s"],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("duration must be between", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stdout, "")

    @unittest.skipIf(os.name == "nt", "POSIX SIGINT; mocked cancellation runs on all platforms")
    def test_real_sigint_cancels_without_traceback(self):
        process = subprocess.Popen(
            [sys.executable, "-m", "alarmclock", "--in", "1h", "--quiet"],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            # Wait for the flushed schedule before sending a signal, avoiding
            # a race with Python startup. A timeout bounds this readiness check.
            import selectors

            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(timeout=5), "alarm did not start")
                self.assertIn("Alarm set", process.stdout.readline())
            process.send_signal(signal.SIGINT)
            output, errors = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 130)
            self.assertIn("Alarm stopped.", output)
            self.assertNotIn("ALARM!", output)
            self.assertEqual(errors, "")
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate()
