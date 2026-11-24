"""Saving news headlines. Only a headline, a short summary, the outlet and a link are kept, never full articles."""
import sqlite3
from datetime import timedelta

from .. import config
from ..timeutil import iso, parse_iso


def save_news(conn: sqlite3.Connection, items: list[dict], now) -> int:
    now_iso = iso(now)
    for it in items:
        conn.execute(
            """INSERT INTO news (url,title,summary,source,published_at,tags,fetched_at)
               VALUES (:url,:title,:summary,:source,:published_at,:tags,:now)
               ON CONFLICT(url) DO UPDATE SET title=excluded.title, summary=excluded.summary, source=excluded.source,
                 published_at=excluded.published_at, tags=excluded.tags, fetched_at=excluded.fetched_at""",
            {**it, "now": now_iso},
        )
    # pruned only after a successful save, so an outage never empties the table
    cutoff = iso(now - timedelta(days=config.NEWS_KEEP_DAYS))
    conn.execute("DELETE FROM news WHERE COALESCE(published_at, fetched_at) < ?", (cutoff,))
    conn.commit()
    return len(items)


def too_old(published_at: str | None, now) -> bool:
    return bool(published_at) and parse_iso(published_at) < now - timedelta(days=config.NEWS_KEEP_DAYS)
