"""Live-data endpoints. Everything is read from SQLite, so these work offline and show saved data."""
import json
import threading
import time
from datetime import timedelta

from fastapi import APIRouter, Depends, Query

from .. import config
from ..connectivity import is_online
from ..db import get_db
from ..geo import bounding_box, haversine_km
from ..ingest import run_all
from ..timeutil import age_minutes, iso, utc_now

router = APIRouter()
SOURCE_NAMES = ("weather", "earthquakes")


def _source_status(db, now):
    rows = {r["source"]: r for r in db.execute("SELECT * FROM sync_log")}
    out = {}
    for name in SOURCE_NAMES:
        r = rows.get(name)
        last_ok = r["last_success_at"] if r else None
        age = age_minutes(last_ok, now)
        out[name] = {
            "last_success_at": last_ok,
            "last_attempt_at": r["last_attempt_at"] if r else None,
            "last_error": r["last_error"] if r else None,
            "age_minutes": age,
            "has_data": last_ok is not None,
            "stale": age is None or age > config.STALE_MINUTES[name],
        }
    return out


def _nearest_weather(db, lat, lng, now):
    rows = db.execute(
        """SELECT w.lat, w.lng, w.payload_json, w.fetched_at FROM weather w
           JOIN (SELECT lat, lng, MAX(fetched_at) mf FROM weather GROUP BY lat, lng) m
             ON w.lat = m.lat AND w.lng = m.lng AND w.fetched_at = m.mf"""
    ).fetchall()
    best = min(rows, key=lambda r: haversine_km(lat, lng, r["lat"], r["lng"]), default=None)
    if best is None:
        return None
    dist = haversine_km(lat, lng, best["lat"], best["lng"])
    if dist > config.WEATHER_MAX_KM:
        return None
    payload = json.loads(best["payload_json"])
    age = age_minutes(best["fetched_at"], now)
    return {**payload, "distance_km": round(dist, 1), "fetched_at": best["fetched_at"],
            "age_minutes": age, "stale": age > config.STALE_MINUTES["weather"]}


def _nearby_quakes(db, lat, lng, radius_km, days, min_mag, now, limit=10):
    min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_km)
    cutoff = iso(now - timedelta(days=days))
    items = []
    for r in db.execute(
        """SELECT ext_id, magnitude, depth_km, lat, lng, place, occurred_at, source, url FROM earthquakes
           WHERE lat BETWEEN ? AND ? AND lng BETWEEN ? AND ? AND occurred_at >= ? AND magnitude >= ?""",
        (min_lat, max_lat, min_lng, max_lng, cutoff, min_mag),
    ):
        d = haversine_km(lat, lng, r["lat"], r["lng"])
        if d <= radius_km:
            items.append({**dict(r), "distance_km": round(d)})
    items.sort(key=lambda q: q["occurred_at"], reverse=True)
    return len(items), items[:limit]


@router.get("/dashboard")
def dashboard(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    quake_radius_km: float = Query(300, gt=0, le=1000),
    quake_days: int = Query(7, ge=1, le=30),
    min_magnitude: float = Query(config.QUAKE_MIN_MAGNITUDE, ge=0, le=10),
    db=Depends(get_db),
):
    now = utc_now()
    sources = _source_status(db, now)
    count, items = _nearby_quakes(db, lat, lng, quake_radius_km, quake_days, min_magnitude, now)
    return {
        "server_time": iso(now),
        "online": is_online(ttl=30),
        "location": {"lat": lat, "lng": lng},
        "sources": sources,
        "weather": _nearest_weather(db, lat, lng, now),
        "earthquakes": {
            "radius_km": quake_radius_km, "days": quake_days, "min_magnitude": min_magnitude,
            "count": count, "items": items,
            "has_data": sources["earthquakes"]["has_data"], "stale": sources["earthquakes"]["stale"],
            "fetched_at": sources["earthquakes"]["last_success_at"], "source": "USGS",
        },
    }


@router.get("/status")
def status(db=Depends(get_db)):
    now = utc_now()
    return {"server_time": iso(now), "online": is_online(ttl=30), "refresh_minutes": config.REFRESH_MINUTES,
            "sources": _source_status(db, now)}


_manual = {"at": 0.0}
_manual_lock = threading.Lock()


@router.post("/refresh")
def refresh_now():
    """Manual 'refresh now' button. Limited to once every 30 s so it can't hammer the data sources."""
    with _manual_lock:
        wait = 30 - (time.monotonic() - _manual["at"])
        if wait > 0:
            return {"status": "cooldown", "retry_in_seconds": int(wait) + 1}
        _manual["at"] = time.monotonic()
    return run_all()
