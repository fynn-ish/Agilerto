"""Live-data endpoints. Everything is read from SQLite, so these work offline and show saved data."""
import json
import threading
import time
from datetime import timedelta

from fastapi import APIRouter, Depends, Query

import re

from .. import config
from ..areas import local_tags
from ..connectivity import is_online
from ..db import get_db
from ..geo import bounding_box, haversine_km
from ..ingest import run_all
from ..timeutil import age_minutes, iso, utc_now

router = APIRouter()
SOURCE_NAMES = ("weather", "earthquakes", "advisories", "news")
GROUP_SOURCES = {"advisories": ("gdacs", "pagasa"), "news": ("rss", "gdelt")}
SOURCE_LABEL = {"gdacs": "GDACS alerts", "pagasa": "PAGASA bulletin page", "rss": "News feeds", "gdelt": "GDELT news index"}
SEVERITY_RANK = {"Bulletin": 4, "Red": 3, "Orange": 2, "Green": 1, "None": 0}


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
        """SELECT lat, lng, payload_json, fetched_at FROM weather
           WHERE id IN (SELECT MAX(id) FROM weather GROUP BY lat, lng)"""     # newest row per city, even if timestamps tie
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


def _source_details(db, now):
    """Health of each individual source, so a broken one shows up as unavailable."""
    rows = {r["source"]: r for r in db.execute("SELECT * FROM sync_log")}
    out = {}
    for group, names in GROUP_SOURCES.items():
        out[group] = []
        for name in names:
            r = rows.get(f"{group}:{name}")
            ok = r["last_success_at"] if r else None
            age = age_minutes(ok, now)
            err = r["last_error"] if r else None
            # A successful run writes the same time to both fields. If they differ, the latest attempt failed.
            failing = bool(r and err and r["last_attempt_at"] != ok)
            out[group].append({
                "name": SOURCE_LABEL[name], "last_success_at": ok, "last_error": err,
                "checked": r is not None, "age_minutes": age,
                "failing": failing,                              # the latest attempt failed
                "note": err if (err and not failing) else None,  # worked, but part of it failed (for example one feed)
            })
    return out


def _advisories(db, lat, lng, now, limit=8):
    cutoff = iso(now - timedelta(hours=config.ADVISORY_MAX_AGE_HOURS))
    items = []
    for r in db.execute("SELECT * FROM advisories WHERE fetched_at >= ?", (cutoff,)):
        d = haversine_km(lat, lng, r["lat"], r["lng"]) if r["lat"] is not None and r["lng"] is not None else None
        items.append({
            "title": r["title"], "body": r["body"], "source": r["source"], "severity": r["severity"],
            "category": r["category"], "area": r["area"], "issued_at": r["issued_at"], "expires_at": r["expires_at"],
            "url": r["url"], "distance_km": round(d) if d is not None else None, "fetched_at": r["fetched_at"],
        })
    items.sort(key=lambda a: (-SEVERITY_RANK.get(a["severity"], 0),
                              a["distance_km"] if a["distance_km"] is not None else 1e9, a["title"]))
    return items[:limit]


def _news(db, lat, lng, now, days, limit=8):
    cutoff = iso(now - timedelta(days=days))
    local = local_tags(lat, lng)
    rows = db.execute(
        "SELECT * FROM news WHERE COALESCE(published_at, fetched_at) >= ?", (cutoff,)).fetchall()
    seen, items = set(), []
    for r in sorted(rows, key=lambda r: r["published_at"] or r["fetched_at"], reverse=True):
        key = re.sub(r"\W+", "", r["title"].lower())               # the same story from several outlets: show it once
        if key in seen:
            continue
        seen.add(key)
        tags = set((r["tags"] or "").split(","))
        items.append({"title": r["title"], "summary": r["summary"], "source": r["source"],
                      "published_at": r["published_at"], "url": r["url"],
                      "local": bool(tags & local), "tags": sorted(t for t in tags if t)})
    items.sort(key=lambda n: not n["local"])                        # local first, newest first within each group (stable sort)
    return len(items), items[:limit]


@router.get("/dashboard")
def dashboard(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    quake_radius_km: float = Query(300, gt=0, le=1000),
    quake_days: int = Query(7, ge=1, le=30),
    min_magnitude: float = Query(config.QUAKE_MIN_MAGNITUDE, ge=0, le=10),
    news_days: int = Query(config.NEWS_SHOW_DAYS, ge=1, le=14),
    db=Depends(get_db),
):
    now = utc_now()
    sources = _source_status(db, now)
    count, items = _nearby_quakes(db, lat, lng, quake_radius_km, quake_days, min_magnitude, now)
    details = _source_details(db, now)
    news_total, news_items = _news(db, lat, lng, now, news_days)
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
        "advisories": {
            "items": _advisories(db, lat, lng, now), "has_data": sources["advisories"]["has_data"],
            "stale": sources["advisories"]["stale"], "fetched_at": sources["advisories"]["last_success_at"],
            "sources": details["advisories"],
        },
        "news": {
            "items": news_items, "total": news_total, "days": news_days, "has_data": sources["news"]["has_data"],
            "stale": sources["news"]["stale"], "fetched_at": sources["news"]["last_success_at"],
            "sources": details["news"],
        },
    }


@router.get("/status")
def status(db=Depends(get_db)):
    now = utc_now()
    return {"server_time": iso(now), "online": is_online(ttl=30), "refresh_minutes": config.REFRESH_MINUTES,
            "sources": _source_status(db, now), "source_details": _source_details(db, now)}


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
    return run_all(force=True)
