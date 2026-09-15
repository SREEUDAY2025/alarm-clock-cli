"""Time parsing and scheduling, independent of terminal I/O."""

import re
import time
from datetime import datetime, timedelta
from typing import Callable

MAX_DURATION = 7 * 24 * 60 * 60
_DURATION = re.compile(r"(?:(\d{1,6})h)?(?:(\d{1,6})m)?(?:(\d{1,6})s)?", re.ASCII)
_CLOCK_TIME = re.compile(r"([0-9]{2}):([0-9]{2})(?::([0-9]{2}))?")


def parse_duration(value: str) -> int:
    """Accept positive integer h/m/s components in that order, up to seven days."""
    match = _DURATION.fullmatch(value)
    if not match or not any(match.groups()):
        raise ValueError("use a duration such as 30s, 10m, or 1h30m (h, m, s order)")
    hours, minutes, seconds = (int(part or 0) for part in match.groups())
    total = hours * 3600 + minutes * 60 + seconds
    if not 1 <= total <= MAX_DURATION:
        raise ValueError("duration must be between 1 second and 7 days")
    return total


def next_occurrence(value: str, now: datetime) -> datetime:
    """Return the next naive local datetime strictly after now."""
    if now.tzinfo is not None:
        raise ValueError("now must be a naive local datetime")
    match = _CLOCK_TIME.fullmatch(value)
    if not match:
        raise ValueError("use local 24-hour time HH:MM or HH:MM:SS")
    hour, minute, second = (int(part or 0) for part in match.groups())
    if hour > 23 or minute > 59 or second > 59:
        raise ValueError("time must be between 00:00:00 and 23:59:59")
    target = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def wait_until(
    deadline: float,
    *,
    clock: Callable[[], float],
    sleep: Callable[[float], None] = time.sleep,
    on_tick: Callable[[float], None] = lambda remaining: None,
) -> None:
    """Recheck the selected clock after each bounded sleep; never fire early."""
    while True:
        remaining = deadline - clock()
        if remaining <= 0:
            return
        on_tick(remaining)
        sleep(min(remaining, 1.0))
