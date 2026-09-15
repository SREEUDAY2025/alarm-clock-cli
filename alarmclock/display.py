"""A compact terminal status view, independent of alarm scheduling."""

import math
import os
import shutil
import sys
import unicodedata
from datetime import datetime


RESET = "\033[0m"
DIM = "\033[90m"
BOLD = "\033[1m"
ACCENT = "\033[36m"


def supports_dashboard() -> bool:
    """Respect explicit plain-output preferences and terminal capabilities."""
    if not sys.stdout.isatty() or os.environ.get("TERM") == "dumb":
        return False
    if "NO_COLOR" in os.environ:
        return False
    try:
        "╭─╮●…".encode(sys.stdout.encoding or "utf-8")
    except UnicodeEncodeError:
        return False
    # Other Windows consoles may not have ANSI processing enabled.
    return os.name != "nt" or bool(os.environ.get("WT_SESSION"))


def cell_width(value: str) -> int:
    return sum(
        0 if unicodedata.combining(char) else
        2 if unicodedata.east_asian_width(char) in "WF" else 1
        for char in value
    )


def fit(value: str, width: int) -> str:
    """Truncate text without splitting a wide character at the terminal edge."""
    if cell_width(value) <= width:
        return value
    result = ""
    for char in value:
        if cell_width(result + char) > max(0, width - 1):
            break
        result += char
    return result + ("…" if width else "")


def clock_text(remaining: float) -> str:
    hours, remainder = divmod(max(0, math.ceil(remaining)), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def setup_header() -> None:
    """A restrained welcome screen; numbered choices work in any terminal."""
    color = supports_dashboard()
    bold, dim, accent, reset = (BOLD, DIM, ACCENT, RESET) if color else ("", "", "", "")
    print(f"\n  {bold}>_ alarmclock{reset}")
    print(f"  {dim}A simple alarm, right here in your terminal.{reset}\n")
    print(f"  {accent}1{reset}  Timer        Ring after a duration, like 10 minutes")
    print(f"  {accent}2{reset}  Alarm        Ring at a local time, like 07:30")
    print(f"  {accent}3{reset}  Quick demo   Start a 5-second alarm\n")
    print(f"  {dim}Type a number, then Enter. Defaults are in [brackets].")
    print(f"  Type q at any step to quit.{reset}\n", flush=True)


class Dashboard:
    def __init__(self, label: str, target: datetime, total: float, quiet: bool):
        self.label = label
        self.target = target
        self.total = max(total, 1)
        self.quiet = quiet

    def open(self) -> None:
        # Keep shell history intact and restore it even when interrupted.
        print("\033[?1049h\033[?25l\033[2J", end="", flush=True)

    def close(self) -> None:
        print(RESET + "\033[?25h\033[?1049l", end="", flush=True)

    def draw(self, remaining: float, *, ringing: bool = False) -> None:
        size = shutil.get_terminal_size((80, 24))
        width = max(8, min(72, size.columns - 4))
        inner = width - 4
        lines = []

        def row(text, style=""):
            text = fit(text, inner)
            padding = " " * (inner - cell_width(text))
            lines.append(DIM + "│ " + RESET + style + text + RESET + padding + DIM + " │" + RESET)

        lines.append(DIM + "╭" + "─" * (width - 2) + "╮" + RESET)
        row(">_ alarmclock", BOLD)
        row("")
        row("alarm    " + self.label)
        row(f"ring at  {self.target:%Y-%m-%d %H:%M:%S} local")
        row("sound    " + ("off" if self.quiet else "terminal bell (may be muted)"))
        lines.append(DIM + "╰" + "─" * (width - 2) + "╯" + RESET)
        lines.append("")
        status = "Alarm ringing" if ringing else "Alarm armed"
        lines.append(ACCENT + "● " + RESET + BOLD + status + RESET)
        lines.append("")
        lines.append("  " + BOLD + clock_text(remaining) + RESET + " remaining")
        progress = min(1.0, max(0.0, 1 - remaining / self.total))
        bar_width = min(28, max(4, width - 12))
        filled = round(progress * bar_width)
        bar = ACCENT + "━" * filled + DIM + "─" * (bar_width - filled)
        lines.append("  " + bar + RESET + f"  {progress:.0%}")
        lines.append("")
        if ringing:
            lines.append(BOLD + fit("ALARM! " + self.label, width) + RESET)
        else:
            lines.append(DIM + f"Local time: {datetime.now():%H:%M:%S}" + RESET)
        lines.append(DIM + fit("Keep this terminal open and your computer awake.", width) + RESET)
        lines.append(DIM + "Ctrl+C to stop" + RESET)

        # Fall back to a few plain lines in a small terminal, without wrapping.
        compact = size.lines < len(lines) + 2 or size.columns < 44
        if compact:
            simple = [">_ alarmclock", status, self.label, clock_text(remaining),
                      f"Ring at {self.target:%H:%M:%S}", "Ctrl+C to stop"]
            lines = [fit(line, max(1, size.columns - 1)) for line in simple]
        output = [RESET, "\033[H"]
        if not compact:
            output.append("\033[2K\n")
        for line in lines[:max(1, size.lines - 1)]:
            output.append("\033[2K" + ("  " if not compact else "") + line + "\n")
        output.append("\033[J")
        print("".join(output), end="", flush=True)
