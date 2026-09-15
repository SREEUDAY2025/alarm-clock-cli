"""Keyboard-driven terminal setup; returns ordinary CLI arguments."""

import codecs
import os
import select
import shutil
import sys
from contextlib import contextmanager
from datetime import datetime

from .core import next_occurrence, parse_duration
from .display import BOLD, RESET, cell_width, fit


@contextmanager
def terminal_screen():
    """Restore both input mode and screen even on cancellation or failure."""
    saved = None
    if os.name != "nt":
        import termios
        import tty
        fd = sys.stdin.fileno()
        saved = termios.tcgetattr(fd)
        tty.setcbreak(fd)
    try:
        print("\033[?1049h\033[?25l\033[48;2;0;0;0m\033[2J", end="", flush=True)
        yield
    finally:
        if saved is not None:
            termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        print(RESET + "\033[?25h\033[?1049l", end="", flush=True)


def read_key():
    """Normalize terminal keys; Escape alone cancels the current view."""
    if os.name == "nt":
        import msvcrt
        key = msvcrt.getwch()
        if key in ("\x00", "\xe0"):
            return {"H": "up", "P": "down"}.get(msvcrt.getwch(), "")
    else:
        decoder = codecs.getincrementaldecoder(sys.stdin.encoding or "utf-8")(errors="replace")
        key = ""
        while not key:
            chunk = os.read(sys.stdin.fileno(), 1)
            if not chunk:
                raise EOFError
            key = decoder.decode(chunk)
        if key == "\x1b":
            # Read bytes directly so TextIO buffering cannot hide an arrow suffix.
            suffix = b""
            for _ in range(2):
                if not select.select([sys.stdin], [], [], 0.05)[0]:
                    break
                suffix += os.read(sys.stdin.fileno(), 1)
            return {b"[A": "up", b"OA": "up", b"[B": "down", b"OB": "down"}.get(suffix, "escape")
    if key == "\x03":
        raise KeyboardInterrupt
    if key in ("", "\x04"):
        raise EOFError
    return {"\r": "enter", "\n": "enter", "\x7f": "backspace", "\b": "backspace", "\x1b": "escape"}.get(key, key)


def paint(title, lines, hint):
    """Draw a stable, opaque terminal page with a compact bordered panel."""
    size = shutil.get_terminal_size((80, 24))
    width = max(10, min(66, size.columns - 4))
    inner = width - 4
    output = ["\033[48;2;0;0;0m\033[H\033[2J", "", f"  {BOLD}>_ alarmclock{RESET}\033[48;2;0;0;0m", "  A simple alarm. Right here.", ""]
    output.append("  ╭" + "─" * (width - 2) + "╮")
    for text, selected in [(title, False), ("", False)] + lines:
        text = fit(text, inner)
        padded = text + " " * max(0, inner - cell_width(text))
        style = "\033[38;2;0;0;0;47m" if selected else "\033[97;48;2;0;0;0m"
        output.append("  │ " + style + padded + RESET + "\033[48;2;0;0;0m │")
    output.extend(["  ╰" + "─" * (width - 2) + "╯", "", "  " + fit(hint, max(1, size.columns - 3))])
    print("\n".join(output[:max(1, size.lines - 1)]), end="", flush=True)


def choose(title, options, *, selected=0, summary=()):
    """Select with arrows and Enter, or a numbered shortcut."""
    while True:
        rows = [(line, False) for line in summary]
        if summary:
            rows.append(("", False))
        rows.extend((f"{'›' if i == selected else ' '} {i + 1}  {option}", i == selected)
                    for i, option in enumerate(options))
        paint(title, rows, "↑ ↓ choose   Enter select   Esc back   Ctrl+C quit")
        key = read_key()
        if key == "up":
            selected = (selected - 1) % len(options)
        elif key in ("down", "\t"):
            selected = (selected + 1) % len(options)
        elif key == "enter":
            return selected
        elif key == "escape":
            return None
        elif key.isascii() and key.isdigit() and 1 <= int(key) <= len(options):
            return int(key) - 1


def edit(title, example, default, validator):
    """Edit one value in place and keep invalid input visible for correction."""
    value = ""
    error = ""
    while True:
        paint(title, [(example, False), ("", False), ((value or f"[{default}]") + "_", True),
                      (error, False)], "Type a value   Enter save   Esc back")
        key = read_key()
        if key == "escape":
            return None
        if key == "enter":
            answer = value or default
            try:
                validator(answer)
                return answer
            except ValueError as exc:
                error = str(exc)
        elif key == "backspace":
            value = value[:-1]
            error = ""
        elif len(key) == 1 and key.isprintable() and len(value) < 80:
            value += key
            error = ""


def setup():
    """Collect a timer or local alarm; optional settings never block starting."""
    # Import at call time to share validators without a module import cycle.
    from .cli import label_text, ring_seconds
    import argparse

    def validate_with(validator):
        def validate(value):
            try:
                validator(value)
            except argparse.ArgumentTypeError as exc:
                raise ValueError(str(exc)) from None
        return validate

    with terminal_screen():
        while True:
            mode = choose("What would you like to set?", ["Timer       After a duration", "Alarm       At a local time", "Quick demo  Five seconds", "Quit"])
            if mode is None or mode == 3:
                return None
            if mode == 2:
                return ["--in", "5s", "--label", "Demo alarm", "--ring-seconds", "2"]
            if mode == 0:
                preset = choose("How long?", ["5 minutes", "10 minutes", "25 minutes", "Custom duration"])
                if preset is None:
                    continue
                when = ["5m", "10m", "25m"][preset] if preset < 3 else edit("Timer duration", "Examples: 30s, 10m, 1h30m", "10m", parse_duration)
                flag = "--in"
            else:
                when = edit("Alarm time", "Local 24-hour time: HH:MM or HH:MM:SS", "07:30",
                            lambda value: next_occurrence(value, datetime.now()))
                flag = "--at"
            if when is None:
                continue
            label, quiet, length = "Alarm", False, "10"
            while True:
                timing = f"After {when}" if flag == "--in" else f"Next local {when} (today or tomorrow)"
                action = choose("Ready to start", ["Start alarm", "Options", "Back"],
                                summary=[timing, f"Label: {label}", f"Sound: {'off' if quiet else 'terminal bell'}  ·  Alert: {length}s"])
                if action is None or action == 2:
                    break
                if action == 0:
                    return [flag, when, "--label", label, "--ring-seconds", length] + (["--quiet"] if quiet else [])
                while True:
                    option = choose("Optional settings", [f"Label          {label}", f"Sound          {'Off' if quiet else 'On'}", f"Alert length   {length}s", "Done"])
                    if option is None or option == 3:
                        break
                    if option == 0:
                        label = edit("Alarm label", "Up to 80 printable characters", label, validate_with(label_text)) or label
                    elif option == 1:
                        quiet = not quiet
                    else:
                        length = edit("Alert length", "Seconds to show the alert (1-60)", length, validate_with(ring_seconds)) or length
