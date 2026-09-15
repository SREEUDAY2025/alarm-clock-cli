# Requirements and implementation plan

Written with AI assistance before application code was created.

## Problem and scope

Build a Python CLI alarm clock during a 30-minute exercise. Favor an understandable,
working vertical slice and evidence of validation over feature count.

The user needs to set one alarm, see when it will fire, and receive an alert.
The process runs in the terminal in the foreground; no web interface, database,
background service, or persistence.

## Acceptance criteria

1. `python3 -m alarmclock --in 10m` fires after ten minutes.
2. `python3 -m alarmclock --at 07:30` fires at the next local occurrence of 07:30.
   A time equal to or earlier than the current time means tomorrow.
   Optional seconds allow a short demonstration.
3. Exactly one of `--in` and `--at` is required. Invalid or zero durations,
   invalid clock times, and invalid alert lengths fail with a helpful CLI error.
4. Show the schedule immediately; show a countdown in an interactive terminal.
   Print a visible alarm message and ring the terminal bell once per second for
   ten seconds by default. `--quiet` disables the bell. `--ring-seconds` controls
   alert length (1–60 seconds). A label provides context.
5. Ctrl+C cancels waiting or ringing cleanly, with exit status 130.
6. Automated tests cover timing without waiting for real minutes or hours.

## Decisions and tradeoffs

- **Standard library only:** argparse, datetime, time, and unittest are sufficient.
  A fresh Python installation can run and test the project without downloads.
- **Two small modules:** core holds parsing, scheduling, and waiting; CLI owns
  arguments and terminal output. Avoid a framework or extensibility scaffolding.
- **Relative versus absolute time:** duration alarms use a monotonic clock;
  time-of-day alarms repeatedly compare with the wall clock. Sleep at most one
  second between checks so interruption and clock changes are noticed promptly.
- **Local time:** use the host's configured timezone. At creation, convert the next
  local date/time into an absolute timestamp. For ambiguous or nonexistent times
  during daylight-saving changes, Python/OS local-time conversion applies.
  Explicit timezone selection and DST disambiguation are outside this exercise.
- **Terminal bell:** portable and dependency-free, but terminals may mute it.
  Always show a visible alert. This application cannot wake a sleeping machine;
  do not promise background delivery. Suspend behavior for duration alarms depends
  on the platform's monotonic clock.
- **Bounded alert:** ring for a fixed duration and exit; avoid threading, input
  loops, and platform-specific keyboard handling in this first version.
- **No persistence, recurrence, multiple alarms, or snooze:** these introduce
  lifecycle and concurrency decisions without being necessary for the core task.

## Planned 30-minute allocation

This is a plan, not a claim about recorded or elapsed build time.

| Minutes | Work |
| --- | --- |
| 0–5 | Refine requirements, acceptance criteria, and tradeoffs with AI |
| 5–17 | Implement parsing, scheduling, wait loop, and CLI alert |
| 17–24 | Review code; test edge cases and run real CLI smoke checks |
| 24–30 | Complete README; demonstrate behavior and explain limitations |

## Validation plan

- Unit tests: duration grammar/bounds, clock parsing, next-day/year rollover,
  monotonic versus wall-clock behavior, clock jumps, and no early firing.
- CLI checks: help, conflicting/missing arguments, visible alert, quiet mode,
  and cancellation with no traceback.
- Run a short real alarm and the complete test suite before handoff.

## AI collaboration

The candidate supplied the exercise brief. Codex proposed this scope and design,
and will generate implementation, tests, and documentation. The candidate should
review those outputs and explain the decisions they accept or change in their
own recording. This document records design rationale; it is not a screen recording.

## Presentation refinement after the initial build

The candidate subsequently requested a more polished interface, explicitly keeping
everything inside the CLI. A separate `display.py` renderer now provides a responsive
compact status panel with a countdown, progress, local/scheduled time, and a distinct
alarm state. The requested style is a restrained, classic terminal interface.
It uses standard ANSI terminal controls and no additional dependencies.
The original two scheduling modes and foreground lifecycle remain the same.

`--plain` and terminal capability checks provide simple output when appropriate.
The dashboard uses the alternate terminal screen and restores screen/cursor state
in a `finally` block, including on Ctrl+C. New tests verify those cleanup and
fallback behaviors. This refinement was requested after the initial implementation;
it was not part of the pre-code plan above.
