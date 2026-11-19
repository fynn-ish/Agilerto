"""Weather from Open-Meteo (free, no API key). Forecast model data, NOT an official PAGASA warning."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import httpx

from .. import config
from ..timeutil import FMT, iso, utc_now
from ..weather_codes import describe
from .base import short_error

URL = "https://api.open-meteo.com/v1/forecast"
CURRENT = ("temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,"
           "weather_code,cloud_cover,pressure_msl,wind_speed_10m,wind_direction_10m,wind_gusts_10m")
DAILY = ("weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
         "precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max")


def fetch_forecast(client: httpx.Client, lat: float, lng: float) -> dict:
    resp = client.get(URL, params={
        "latitude": lat, "longitude": lng, "current": CURRENT, "daily": DAILY,
        "timezone": "auto", "forecast_days": 3,
    })
    resp.raise_for_status()
    return resp.json()


def _at(seq, i):
    try:
        return seq[i]
    except (TypeError, IndexError):
        return None


def parse_forecast(area: str, raw: dict) -> dict:
    """Open-Meteo response -> the small, stable shape we store and show. Missing fields become None."""
    cur = raw.get("current") or {}
    daily = raw.get("daily") or {}
    offset = int(raw.get("utc_offset_seconds") or 0)

    observed_at = None
    if cur.get("time"):                       # local time without offset, e.g. 2026-11-11T15:30
        local = datetime.strptime(cur["time"], "%Y-%m-%dT%H:%M")
        observed_at = (local - timedelta(seconds=offset)).replace(tzinfo=timezone.utc).strftime(FMT)

    days = []
    for i, date in enumerate(daily.get("time") or []):
        code = _at(daily.get("weather_code"), i)
        days.append({
            "date": date,
            "condition": describe(code),
            "weather_code": code,
            "temp_max_c": _at(daily.get("temperature_2m_max"), i),
            "temp_min_c": _at(daily.get("temperature_2m_min"), i),
            "rain_sum_mm": _at(daily.get("precipitation_sum"), i),
            "rain_chance_pct": _at(daily.get("precipitation_probability_max"), i),
            "wind_max_kph": _at(daily.get("wind_speed_10m_max"), i),
            "gust_max_kph": _at(daily.get("wind_gusts_10m_max"), i),
        })

    code = cur.get("weather_code")
    return {
        "area": area,
        "source": "Open-Meteo",
        "observed_at": observed_at,
        "timezone": raw.get("timezone"),
        "current": {
            "temp_c": cur.get("temperature_2m"),
            "feels_like_c": cur.get("apparent_temperature"),
            "humidity_pct": cur.get("relative_humidity_2m"),
            "rain_mm": cur.get("precipitation"),
            "weather_code": code,
            "condition": describe(code),
            "cloud_cover_pct": cur.get("cloud_cover"),
            "pressure_hpa": cur.get("pressure_msl"),
            "wind_kph": cur.get("wind_speed_10m"),
            "wind_dir_deg": cur.get("wind_direction_10m"),
            "gust_kph": cur.get("wind_gusts_10m"),
        },
        "daily": days,
    }


def refresh(conn: sqlite3.Connection, client: httpx.Client, now=None) -> dict:
    """Fetch every configured area. One failing area does not stop the others."""
    now_iso = iso(now or utc_now())
    saved, errors = 0, []
    for area in config.AREAS:
        try:
            payload = parse_forecast(area["name"], fetch_forecast(client, area["lat"], area["lng"]))
            conn.execute(
                "INSERT INTO weather (lat, lng, payload_json, fetched_at) VALUES (?,?,?,?)",
                (area["lat"], area["lng"], json.dumps(payload), now_iso),
            )
            # keep only the newest N snapshots for this area
            conn.execute(
                """DELETE FROM weather WHERE lat=? AND lng=? AND id NOT IN
                   (SELECT id FROM weather WHERE lat=? AND lng=? ORDER BY fetched_at DESC, id DESC LIMIT ?)""",
                (area["lat"], area["lng"], area["lat"], area["lng"], config.WEATHER_KEEP_SNAPSHOTS),
            )
            conn.commit()
            saved += 1
        except Exception as exc:        # network error, bad status, bad JSON: keep going
            conn.rollback()
            errors.append(f"{area['name']}: {short_error(exc)}")
    return {"saved": saved, "errors": errors}
