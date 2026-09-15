"""Command-line arguments, countdown, and bounded terminal alert."""

import argparse
import math
import sys
import time
from datetime import datetime, timedelta

from .core import next_occurrence, parse_duration, wait_until
from .display import Dashboard, setup_header, supports_dashboard


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
            "Run without arguments in a terminal for guided setup.\n\n"
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


def guided_setup() -> list[str] | None:
    """Collect arguments interactively, reusing the command's validators."""
    def ask(prompt, validate, default=None):
        while True:
            suffix = f" [{default}]" if default is not None else ""
            value = input(f"  {prompt}{suffix}: ").strip()
            if value.lower() == "q":
                return None
            if not value and default is not None:
                value = default
            try:
                validate(value)
                return value
            except (ValueError, argparse.ArgumentTypeError) as exc:
                print(f"  {exc}. Please try again.\n", flush=True)

    def choice(options):
        def validate(value):
            if value.lower() not in options:
                raise ValueError("choose " + " or ".join(options))
        return validate

    setup_header()
    mode = ask("Choose", choice(("1", "2", "3")), "1")
    if mode is None:
        return None
    if mode == "3":
        return ["--in", "5s", "--label", "Demo alarm", "--ring-seconds", "2"]
    if mode == "1":
        print("\n  TIMER\n")
        when = ask("How long? (30s, 10m, 1h30m)", parse_duration, "10m")
        flag = "--in"
    else:
        print(f"\n  ALARM  /  Local time now: {datetime.now():%H:%M:%S}")
        print("  A time that has passed will ring tomorrow.\n")
        when = ask("What time? (24-hour HH:MM or HH:MM:SS)",
                   lambda value: next_occurrence(value, datetime.now()))
        flag = "--at"
    if when is None:
        return None
    label = ask("Label (optional)", label_text, "Alarm")
    if label is None:
        return None
    sound = ask("Sound the terminal bell? (y/n)", choice(("y", "n")), "y")
    if sound is None:
        return None
    if sound.lower() == "y":
        print("  Your terminal may mute the bell; a visible alert is always shown.")
    length = ask("Alert duration in seconds (1-60)", ring_seconds, "10")
    if length is None:
        return None
    timing = f"after {when}" if flag == "--in" else f"at the next local {when}"
    print("\n  READY TO START\n")
    print(f"  Alarm    {label}")
    print(f"  When     {timing}")
    print(f"  Sound    {'on' if sound.lower() == 'y' else 'off'}")
    print(f"  Alert    {length} second{'s' if int(length) != 1 else ''}")
    print("\n  Keep this terminal open and your computer awake.\n")
    confirm = ask("Start alarm? (y/n)", choice(("y", "n")), "y")
    if confirm is None or confirm.lower() == "n":
        return None
    args = [flag, when, "--label", label, "--ring-seconds", length]
    if sound.lower() == "n":
        args.append("--quiet")
    return args


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
            unit = "second" if seconds == 1 else "seconds"
            schedule = f"in {seconds} {unit} (about {target:%Y-%m-%d %H:%M:%S} local)"
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
    arguments = list(sys.argv[1:] if argv is None else argv)
    setting_up = False
    try:
        if not arguments and sys.stdin.isatty() and sys.stdout.isatty():
            setting_up = True
            arguments = guided_setup()
            if arguments is None:
                print("Setup cancelled. No alarm was started.", flush=True)
                return 0
            setting_up = False
        args = parser.parse_args(arguments)
        return run(args, parser)
    except EOFError:
        print("\nSetup cancelled. No alarm was started.", flush=True)
        return 0
    except KeyboardInterrupt:
        message = "Setup cancelled. No alarm was started." if setting_up else "Alarm stopped."
        print("\n" + message, flush=True)
        return 130
