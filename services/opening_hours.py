import os
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def day_index(day: str) -> int:
    """monday -> 0 ... sunday -> 6 (used for sorting)."""
    return DAYS.index(day) if day in DAYS else 7


def now_local() -> datetime:
    return datetime.now(ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Bahrain")))


def branch_is_open_now(branch, now: Optional[datetime] = None) -> bool:
    """True if the branch is active and today's hours include the current time.

    Also handles hours that go past midnight, e.g. 20:00 to 02:00.
    """
    if not branch.is_active:
        return False

    now = now or now_local()
    today = DAYS[now.weekday()]
    yesterday = DAYS[(now.weekday() - 1) % 7]
    current = now.time()

    for hour in branch.operating_hours:
        if hour.is_closed or not hour.open_time or not hour.close_time:
            continue

        if hour.open_time < hour.close_time:
            # Normal day, e.g. 09:00 to 17:00
            if hour.day_of_week == today and hour.open_time <= current < hour.close_time:
                return True
        else:
            # Past midnight, e.g. 20:00 to 02:00
            if hour.day_of_week == today and current >= hour.open_time:
                return True
            if hour.day_of_week == yesterday and current < hour.close_time:
                return True

    return False