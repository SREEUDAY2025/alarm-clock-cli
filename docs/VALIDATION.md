# Validation

## Local checks — 2026-09-15

Environment: macOS, Python 3.14.5.

| Check | Observed result |
| --- | --- |
| `python3 -m unittest discover -v` | All 23 tests passed in approximately 2.2 seconds |
| `python3 -m alarmclock --help` | Clear options and separate runnable examples; exit 0 |
| Interactive `--in 2s --label 'Stretch break' --ring-seconds 1` | Countdown showed 2 then 1; visible alert, one bell character, completion; exit 0 |
| Real `--at` alarm approximately three seconds ahead, with `--quiet --ring-seconds 1` | Displayed the resolved IST time/UTC offset, fired, and completed; exit 0 |
| Real-process invalid `--in 0s` | Helpful stderr error, exit 2, no traceback |
| Real-process one-hour alarm interrupted with SIGINT | Stopped promptly, exit 130, no traceback |

The last two checks are part of the automated integration suite. Fake clocks
exercise clock adjustments without altering the host clock. The real alarm test
checks the total elapsed delay plus alert time, while the fake-clock test checks
that waiting does not return before the deadline.

Terminal output confirmed that the bell character was emitted. Audibility depends
on the user's terminal and speakers and was not verified by these checks.

## CI

The workflow runs the suite on Linux (Python 3.10 and 3.14), macOS (3.14), and
Windows (3.14). A configured workflow alone is not evidence of a passing run;
check the repository's Actions tab for the results of the published commit.

[The initial published run](https://github.com/SREEUDAY2025/alarm-clock-cli/actions/runs/34950788327)
passed all four jobs for commit `2c1e188`. GitHub reported deprecated runtime
warnings for the original checkout/setup actions; those action references were
subsequently updated to the current official release tags. Application code did
not change in that workflow maintenance step.

## Remaining boundaries

- Sleep/wake delivery and OS-specific daylight-saving disambiguation are documented
  limitations, not validated reliability guarantees.
- Windows console Ctrl+C is covered by mocked handler tests; the real SIGINT
  subprocess test runs only on POSIX systems.
