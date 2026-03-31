"""Central timezone configuration for Gilbertus.

Change APP_TIMEZONE here to update timezone across the entire system.
All modules import from this file — never hardcode timezone elsewhere.
"""
from zoneinfo import ZoneInfo

APP_TIMEZONE_NAME = 'Europe/Warsaw'  # CET/CEST
APP_TIMEZONE = ZoneInfo(APP_TIMEZONE_NAME)


def now():
    """Current datetime in app timezone (CET)."""
    from datetime import datetime
    return datetime.now(APP_TIMEZONE)


def today():
    """Current date in app timezone (CET)."""
    return now().date()


def to_app_tz(dt):
    """Convert any datetime to app timezone."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        from datetime import timezone
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(APP_TIMEZONE)
