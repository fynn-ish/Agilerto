"""Earthquakes from the USGS feed (free, no key). USGS may list small local quakes late or not at all;
PHIVOLCS is the official Philippine source and can be added later as a second source."""
import sqlite3
from datetime import timedelta

import httpx

from .. import config
from ..timeutil import from_epoch_ms, iso, utc_now

URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"


def fetch_events(client: httpx.Client, now) -> dict:
    resp = client.get(URL, params={
        "format": "geojson",
        "starttime": (now - timedelta(days=config.QUAKE_FETCH_DAYS)).strftime("%Y-%m-%dT%H:%M:%S"),
        "minmagnitude": config.QUAKE_MIN_MAGNITUDE,
        "orderby": "time",
        "limit": 500,
        **config.QUAKE_REGION,
    })
    resp.raise_for_status()
    return resp.json()


def parse_events(geojson: dict) -> list[dict]:
    events = []
    for f in geojson.get("features", []):
        props = f.get("properties") or {}
        coords = (f.get("geometry") or {}).get("coordinates") or []
        if props.get("type") not in (None, "earthquake") or len(coords) < 2:
            continue                          # skip quarry blasts etc. and malformed rows
        if props.get("mag") is None or props.get("time") is None or not f.get("id"):
            continue
        events.append({
            "ext_id": f["id"],
            "magnitude": props["mag"],
            "depth_km": coords[2] if len(coords) > 2 else None,
            "lat": coords[1],
            "lng": coords[0],
            "place": props.get("place"),
            "occurred_at": iso(from_epoch_ms(props["time"])),
            "url": props.get("url"),
        })
    return events


def refresh(conn: sqlite3.Connection, client: httpx.Client, now=None) -> dict:
    now = now or utc_now()
    now_iso = iso(now)
    events = parse_events(fetch_events(client, now))        # raises on failure; caller logs it
    for e in events:
        conn.execute(
            """INSERT INTO earthquakes (ext_id,magnitude,depth_km,lat,lng,place,occurred_at,source,url,fetched_at)
               VALUES (:ext_id,:magnitude,:depth_km,:lat,:lng,:place,:occurred_at,'USGS',:url,:now)
               ON CONFLICT(ext_id) DO UPDATE SET magnitude=excluded.magnitude, depth_km=excluded.depth_km,
                 lat=excluded.lat, lng=excluded.lng, place=excluded.place, url=excluded.url,
                 fetched_at=excluded.fetched_at""",          # USGS revises events, so update in place
            {**e, "now": now_iso},
        )
    # prune only after a successful fetch, so an outage never empties the table
    cutoff = iso(now - timedelta(days=config.QUAKE_RETENTION_DAYS))
    conn.execute("DELETE FROM earthquakes WHERE occurred_at < ?", (cutoff,))
    conn.commit()
    return {"saved": len(events), "errors": []}
