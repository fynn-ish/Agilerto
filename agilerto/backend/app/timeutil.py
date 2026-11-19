"""All timestamps are stored as UTC ISO strings ending in Z, e.g. 2026-11-11T07:30:00Z."""
from datetime import datetime, timezone

FMT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(FMT)


def parse_iso(s: str) -> datetime:
    return datetime.strptime(s, FMT).replace(tzinfo=timezone.utc)


def from_epoch_ms(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, timezone.utc)


def age_minutes(ts, now=None):
    """Minutes since an ISO timestamp, or None if there is no timestamp."""
    if not ts:
        return None
    now = now or utc_now()
    return max(0, int((now - parse_iso(ts)).total_seconds() // 60))
