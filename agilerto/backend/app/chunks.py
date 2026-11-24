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
        article = "an" if label[0] in "aeiou" else "a"
        parts = [f"{r['name']} is {article} {label}."]
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
        """SELECT lat, lng, payload_json, fetched_at FROM weather
           WHERE id IN (SELECT MAX(id) FROM weather GROUP BY lat, lng)"""     # newest row per city, even if timestamps tie
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


# ---------- advisories and news (Step 4) ----------
_CATEGORY_LABEL = {"tropical_cyclone": "tropical cyclone", "flood": "flood", "volcano": "volcano", "status": "status"}


def _short_date(ts):
    return ts.replace("T", " ").replace("Z", "")[:16] + " UTC" if ts else None


def rebuild_advisory_chunks(conn: sqlite3.Connection) -> int:
    from datetime import timedelta
    from . import config
    conn.execute("DELETE FROM chunks WHERE kind = 'advisory'")
    cutoff = _iso(_utc_now() - _td(hours=config.ADVISORY_MAX_AGE_HOURS))
    n = 0
    for r in conn.execute("SELECT * FROM advisories WHERE fetched_at >= ?", (cutoff,)):
        if r["source"] == "GDACS":
            text = (f"Advisory from GDACS ({r['severity']} alert, {_CATEGORY_LABEL.get(r['category'], 'event')}): "
                    f"{r['title']} {r['body'] or ''}")
            if r["issued_at"]:
                text += f" Last updated {_short_date(r['issued_at'])}."
            text += (" GDACS is an automated alert system of the UN and European Commission. "
                     "It is not an official Philippine government warning.")
        else:
            text = f"{r['source']}: {r['title']}. {r['body'] or ''}"
        conn.execute(
            "INSERT INTO chunks (kind, ref_id, title, text, lat, lng, source, fetched_at) VALUES (?,?,?,?,?,?,?,?)",
            ("advisory", r["ext_id"], r["title"][:120], text.strip(), r["lat"], r["lng"], r["source"], r["fetched_at"]),
        )
        n += 1
    return n


def rebuild_news_chunks(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM chunks WHERE kind = 'news'")
    row = conn.execute("SELECT last_success_at FROM sync_log WHERE source = 'news'").fetchone()
    checked = row["last_success_at"] if row else None       # when the news sources were last read, not when each story ran
    n = 0
    for r in conn.execute("SELECT * FROM news"):
        when = _short_date(r["published_at"]) or "an unknown date"
        text = f"News headline reported by {r['source'] or 'a news outlet'} on {when}: {r['title']}."
        if r["summary"]:
            text += f" {r['summary']}"
        text += " This is a news report and has not been verified by this system."
        conn.execute(
            "INSERT INTO chunks (kind, ref_id, title, text, source, fetched_at) VALUES (?,?,?,?,?,?)",
            ("news", r["url"], r["title"][:120], text, r["source"], checked or r["fetched_at"]),
        )
        n += 1
    return n
