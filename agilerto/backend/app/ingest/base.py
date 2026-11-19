"""sync_log bookkeeping shared by every data source."""
import sqlite3

import httpx


def short_error(exc: Exception) -> str:
    """One short, readable line instead of a 600-character URL dump."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    if isinstance(exc, httpx.TimeoutException):
        return "timed out"
    if isinstance(exc, httpx.TransportError):
        return "connection failed"
    return f"{type(exc).__name__}: {str(exc)[:100]}"


def mark_success(conn: sqlite3.Connection, source: str, now_iso: str, note: str | None = None):
    """`note` records a partial problem (e.g. 2 of 10 areas failed) without hiding the success."""
    conn.execute(
        """INSERT INTO sync_log (source, last_success_at, last_attempt_at, last_error)
           VALUES (?,?,?,?)
           ON CONFLICT(source) DO UPDATE SET last_success_at=excluded.last_success_at,
             last_attempt_at=excluded.last_attempt_at, last_error=excluded.last_error""",
        (source, now_iso, now_iso, note[:500] if note else None),
    )
    conn.commit()


def mark_failure(conn: sqlite3.Connection, source: str, now_iso: str, error: str):
    """Records the failure but leaves last_success_at (and all saved data) untouched."""
    conn.execute(
        """INSERT INTO sync_log (source, last_attempt_at, last_error) VALUES (?,?,?)
           ON CONFLICT(source) DO UPDATE SET last_attempt_at=excluded.last_attempt_at,
             last_error=excluded.last_error""",
        (source, now_iso, error[:500]),
    )
    conn.commit()
