"""Turn static records into text chunks for RAG (Step 3 will search these with FTS5)."""
import sqlite3

TYPE_LABEL = {
    "hospital": "hospital",
    "evacuation_center": "evacuation center",
    "fire_station": "fire station",
    "police_station": "police station",
}
STATIC_KINDS = ("facility", "hotline", "guide")


def rebuild_static_chunks(conn: sqlite3.Connection) -> dict:
    """Replace all static chunks from the current tables. Run after seeding or importing."""
    conn.execute(f"DELETE FROM chunks WHERE kind IN ({','.join('?' * len(STATIC_KINDS))})", STATIC_KINDS)
    counts = {"facility": 0, "hotline": 0, "guide": 0}

    for r in conn.execute("SELECT * FROM facilities"):
        label = TYPE_LABEL[r["type"]]
        parts = [f"{r['name']} is a {label}."]
        if r["address"]:
            parts.append(f"Address: {r['address']}.")
        if r["phone"]:
            parts.append(f"Phone: {r['phone']}.")
        if r["capacity"]:
            parts.append(f"Capacity: about {r['capacity']} people.")
        if not r["verified"]:
            parts.append("This record is not yet verified.")
        conn.execute(
            "INSERT INTO chunks (kind, ref_id, title, text, lat, lng, source) VALUES (?,?,?,?,?,?,?)",
            ("facility", r["ref"], r["name"], " ".join(parts), r["lat"], r["lng"], r["source"]),
        )
        counts["facility"] += 1

    for r in conn.execute("SELECT * FROM emergency_numbers"):
        text = f"Emergency hotline: {r['agency']} ({r['area']}): {r['number']}."
        if r["notes"]:
            text += f" {r['notes']}."
        conn.execute(
            "INSERT INTO chunks (kind, ref_id, title, text, source) VALUES (?,?,?,?,?)",
            ("hotline", r["ref"], r["agency"], text, r["source"]),
        )
        counts["hotline"] += 1

    for r in conn.execute("SELECT * FROM safety_guides"):
        text = f"{r['title']} ({r['hazard']}, {r['phase']}). {r['body']}"
        conn.execute(
            "INSERT INTO chunks (kind, ref_id, title, text, source) VALUES (?,?,?,?,?)",
            ("guide", r["ref"], r["title"], text, r["source"]),
        )
        counts["guide"] += 1

    return counts


# ---------- live data chunks (rebuilt after each successful refresh) ----------
import json as _json
from datetime import timedelta as _td

from .timeutil import iso as _iso, utc_now as _utc_now


def _f(v, unit="", nd=0):
    return "unknown" if v is None else f"{round(v, nd) if nd else round(v)}{unit}"


def rebuild_weather_chunks(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM chunks WHERE kind = 'weather'")
    rows = conn.execute(
        """SELECT w.lat, w.lng, w.payload_json, w.fetched_at FROM weather w
           JOIN (SELECT lat, lng, MAX(fetched_at) mf FROM weather GROUP BY lat, lng) m
             ON w.lat = m.lat AND w.lng = m.lng AND w.fetched_at = m.mf"""
    ).fetchall()
    n = 0
    for r in rows:
        p = _json.loads(r["payload_json"])
        c = p["current"]
        text = (f"Weather for {p['area']}: {c['condition']}, {_f(c['temp_c'], ' C')} "
                f"(feels like {_f(c['feels_like_c'], ' C')}). Humidity {_f(c['humidity_pct'], '%')}. "
                f"Wind {_f(c['wind_kph'], ' km/h')}, gusts {_f(c['gust_kph'], ' km/h')}. "
                f"Rain now {_f(c['rain_mm'], ' mm', 1)}.")
        for d in p["daily"]:
            text += (f" Forecast {d['date']}: {d['condition']}, {_f(d['temp_min_c'])} to {_f(d['temp_max_c'], ' C')}, "
                     f"rain chance {_f(d['rain_chance_pct'], '%')}, rain {_f(d['rain_sum_mm'], ' mm', 1)}.")
        text += " This is forecast model data from Open-Meteo, not an official PAGASA warning."
        conn.execute(
            "INSERT INTO chunks (kind, ref_id, title, text, lat, lng, source, fetched_at) VALUES (?,?,?,?,?,?,?,?)",
            ("weather", p["area"], f"Weather: {p['area']}", text, r["lat"], r["lng"], "Open-Meteo", r["fetched_at"]),
        )
        n += 1
    return n


def rebuild_quake_chunks(conn: sqlite3.Connection, days: int = 7, limit: int = 100) -> int:
    conn.execute("DELETE FROM chunks WHERE kind = 'quake'")
    cutoff = _iso(_utc_now() - _td(days=days))
    n = 0
    for r in conn.execute(
        "SELECT * FROM earthquakes WHERE occurred_at >= ? ORDER BY occurred_at DESC LIMIT ?", (cutoff, limit)
    ):
        depth = f", depth {_f(r['depth_km'], ' km')}" if r["depth_km"] is not None else ""
        text = (f"Earthquake magnitude {r['magnitude']} {r['place'] or 'location unknown'}{depth}, "
                f"occurred {r['occurred_at']} UTC (source: {r['source']}).")
        conn.execute(
            "INSERT INTO chunks (kind, ref_id, title, text, lat, lng, source, fetched_at) VALUES (?,?,?,?,?,?,?,?)",
            ("quake", r["ext_id"], f"M{r['magnitude']} {r['place'] or ''}".strip(), text,
             r["lat"], r["lng"], r["source"], r["fetched_at"]),
        )
        n += 1
    return n
