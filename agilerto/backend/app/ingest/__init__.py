"""Runs every data source. Rules: skip when offline, never delete old data on failure, log what happened.

Sources are grouped (weather, earthquakes, advisories, news). Inside a group each source fails on its own,
so a blocked news feed never stops the others, and the group counts as refreshed if any source worked."""
import logging
import threading

import httpx

from .. import config
from ..chunks import (rebuild_advisory_chunks, rebuild_news_chunks, rebuild_quake_chunks,
                      rebuild_weather_chunks)
from ..connectivity import is_online
from ..db import connect
from ..timeutil import age_minutes, iso, utc_now
from . import earthquakes, gdacs, gdelt, pagasa, rss_news, weather
from .base import mark_failure, mark_success, short_error

log = logging.getLogger("uvicorn.error.ingest")
_run_lock = threading.Lock()

GROUPS = (
    ("weather", (weather,), rebuild_weather_chunks),
    ("earthquakes", (earthquakes,), rebuild_quake_chunks),
    ("advisories", (gdacs, pagasa), rebuild_advisory_chunks),
    ("news", (rss_news, gdelt), rebuild_news_chunks),
)


def _checked_recently(conn, group, now) -> bool:
    minutes = config.SOURCE_MIN_INTERVAL_MINUTES.get(group)
    if not minutes:
        return False
    row = conn.execute("SELECT last_attempt_at FROM sync_log WHERE source = ?", (group,)).fetchone()
    age = age_minutes(row["last_attempt_at"], now) if row else None
    return age is not None and age < minutes * 0.9


def _run_group(conn, client, group, modules, rebuild_chunks, now, force):
    if not force and _checked_recently(conn, group, now):
        return {"ok": True, "skipped": "checked recently", "saved": 0, "errors": []}
    now_iso = iso(now)
    saved, errors, any_ok = 0, [], False
    for mod in modules:
        name = getattr(mod, "NAME", None)
        label = f"{group}:{name}" if name else group
        try:
            r = mod.refresh(conn, client, now)
            errs = r.get("errors", [])
            if r["saved"] == 0 and errs:
                raise RuntimeError("; ".join(errs))
            any_ok, saved = True, saved + r["saved"]
            errors += errs
            if name:
                mark_success(conn, label, now_iso, "; ".join(errs) or None)
        except Exception as exc:
            conn.rollback()
            msg = str(exc) if isinstance(exc, RuntimeError) else short_error(exc)
            errors.append(f"{name}: {msg}" if name else msg)
            if name:
                mark_failure(conn, label, now_iso, msg)
    if any_ok:
        mark_success(conn, group, now_iso, "; ".join(errors) or None)    # partial failures are noted, not hidden
        rebuild_chunks(conn)
        conn.commit()
        log.info("%s: saved %d record(s)%s", group, saved, f", {len(errors)} error(s)" if errors else "")
        return {"ok": True, "saved": saved, "errors": errors}
    mark_failure(conn, group, now_iso, "; ".join(errors))
    log.warning("%s: refresh failed, keeping saved data (%s)", group, "; ".join(errors)[:200])
    return {"ok": False, "saved": 0, "errors": errors, "error": "; ".join(errors)}


def run_all(online_check=None, client: httpx.Client | None = None, now=None, only=None, force: bool = False) -> dict:
    """Refresh every source once. `only` limits the run to some group or source names, for example {"gdacs"}.
    `online_check` and `client` can be replaced in tests. `force` ignores the minimum interval."""
    if not _run_lock.acquire(blocking=False):
        return {"status": "busy"}
    try:
        online = (online_check or (lambda: is_online(force=True)))()
        if not online:
            log.info("Offline: skipping refresh, saved data is kept as it is")
            return {"status": "offline"}

        own_client = client is None
        client = client or httpx.Client(timeout=config.HTTP_TIMEOUT, headers={"User-Agent": config.USER_AGENT})
        conn = connect()
        try:
            now = now or utc_now()
            only = {o.lower() for o in only} if only else None
            results = {}
            for group, modules, rebuild in GROUPS:
                chosen = [m for m in modules if not only or group in only or getattr(m, "NAME", None) in only]
                if chosen:
                    results[group] = _run_group(conn, client, group, chosen, rebuild, now, force or bool(only))
            return {"status": "ok", "refreshed_at": iso(now), **results}
        finally:
            conn.close()
            if own_client:
                client.close()
    finally:
        _run_lock.release()
