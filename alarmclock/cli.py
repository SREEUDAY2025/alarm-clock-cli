"""Command-line arguments, countdown, and bounded terminal alert."""

import argparse
import math
import sys
import time
from datetime import datetime, timedelta

from .core import next_occurrence, parse_duration, wait_until
from .display import Dashboard, supports_dashboard


def ring_seconds(value: str) -> int:
    try:
        result = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "ring duration must be an integer from 1 to 60"
        ) from None
    if not 1 <= result <= 60:
        raise argparse.ArgumentTypeError("ring duration must be an integer from 1 to 60")
    return result


def label_text(value: str) -> str:
    if not value.strip() or len(value) > 80 or not value.isprintable():
        raise argparse.ArgumentTypeError("label must contain 1–80 printable characters")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alarmclock",
        description="Set one foreground alarm. Keep this terminal open and the computer awake.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 -m alarmclock --in 10m\n"
            "  python3 -m alarmclock --at 07:30"
        ),
    )
    when = parser.add_mutually_exclusive_group(required=True)
    when.add_argument(
        "--in", dest="duration", metavar="DURATION",
        help="delay: 30s, 10m, 1h30m (up to 7 days)",
    )
    when.add_argument(
        "--at", metavar="HH:MM[:SS]",
        help="next occurrence in local 24-hour time",
    )
    parser.add_argument(
        "--label", type=label_text, default="Alarm",
        help="alarm message (up to 80 characters)",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="show the alarm without sounding the terminal bell",
    )
    parser.add_argument(
        "--plain", action="store_true",
        help="use simple text instead of the terminal status panel",
    )
    parser.add_argument(
        "--ring-seconds", type=ring_seconds, default=10, metavar="1-60",
        help="alert length in seconds (default: 10)",
    )
    return parser


def countdown(remaining: float) -> None:
    hours, remainder = divmod(math.ceil(remaining), 3600)
    minutes, seconds = divmod(remainder, 60)
    print(f"\rTime remaining: {hours:02}:{minutes:02}:{seconds:02}   ", end="", flush=True)


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        if args.duration is not None:
            seconds = parse_duration(args.duration)
            clock = time.monotonic
            deadline = clock() + seconds
            target = datetime.now() + timedelta(seconds=seconds)
            schedule = f"in {seconds} seconds (about {target:%Y-%m-%d %H:%M:%S} local)"
        else:
            target = next_occurrence(args.at, datetime.now())
            clock = time.time
            deadline = target.timestamp()
            # Display the OS-resolved time, including its UTC offset around DST.
            resolved = datetime.fromtimestamp(deadline).astimezone()
            target = resolved
            schedule = f"at {resolved:%Y-%m-%d %H:%M:%S %Z (%z)}"
    except ValueError as exc:
        parser.error(str(exc))

    print(f"Alarm set {schedule}: {args.label}", flush=True)
    print("Keep this process running. Press Ctrl+C to cancel or stop the alert.", flush=True)
    if not args.quiet:
        print("Sound uses the terminal bell; your terminal may mute it.", flush=True)
    dashboard = None
    if not args.plain and supports_dashboard():
        dashboard = Dashboard(args.label, target, deadline - clock(), args.quiet)
    try:
        if dashboard:
            dashboard.open()
        tick = dashboard.draw if dashboard else countdown
        kwargs = {"on_tick": tick} if sys.stdout.isatty() else {}
        wait_until(deadline, clock=clock, **kwargs)
        if not dashboard:
            if sys.stdout.isatty():
                print("\r" + " " * 60 + "\r", end="", flush=True)
            print(f"ALARM! {args.label}", flush=True)
        for _ in range(args.ring_seconds):
            if dashboard:
                dashboard.draw(0, ringing=True)
            if not args.quiet:
                print("\a", end="", flush=True)
            time.sleep(1)
    finally:
        if dashboard:
            dashboard.close()
    if dashboard:
        print(f"ALARM! {args.label}", flush=True)
    print("Alarm finished.", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args, parser)
    except KeyboardInterrupt:
        print("\nAlarm stopped.", flush=True)
        return 130
