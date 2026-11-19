"""Runs every data source. Rules: skip when offline, never delete old data on failure, log what happened."""
import logging
import threading

import httpx

from .. import config
from ..chunks import rebuild_quake_chunks, rebuild_weather_chunks
from ..connectivity import is_online
from ..db import connect
from ..timeutil import iso, utc_now
from . import earthquakes, weather
from .base import mark_failure, mark_success, short_error

log = logging.getLogger("uvicorn.error.ingest")
_run_lock = threading.Lock()

SOURCES = (
    ("weather", weather, rebuild_weather_chunks),
    ("earthquakes", earthquakes, rebuild_quake_chunks),
)


def _run_source(conn, client, name, module, rebuild_chunks, now):
    now_iso = iso(now)
    try:
        result = module.refresh(conn, client, now)
        errors = result.get("errors", [])
        if result["saved"] == 0 and errors:
            raise RuntimeError("; ".join(errors))
        mark_success(conn, name, now_iso, "; ".join(errors) or None)   # partial failures are noted, not hidden
        rebuild_chunks(conn)
        conn.commit()
        log.info("%s: saved %d record(s)%s", name, result["saved"], f", {len(errors)} error(s)" if errors else "")
        return {"ok": True, **result}
    except Exception as exc:
        conn.rollback()
        msg = str(exc) if isinstance(exc, RuntimeError) else short_error(exc)
        mark_failure(conn, name, now_iso, msg)
        log.warning("%s: refresh failed, keeping saved data (%s)", name, msg[:200])
        return {"ok": False, "error": msg}


def run_all(online_check=None, client: httpx.Client | None = None, now=None) -> dict:
    """Refresh every source once. `online_check` and `client` can be replaced in tests."""
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
            results = {name: _run_source(conn, client, name, mod, rebuild, now) for name, mod, rebuild in SOURCES}
            return {"status": "ok", "refreshed_at": iso(now), **results}
        finally:
            conn.close()
            if own_client:
                client.close()
    finally:
        _run_lock.release()
