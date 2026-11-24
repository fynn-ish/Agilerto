"""GDACS (Global Disaster Alert and Coordination System, UN + European Commission).
Automated alerts for cyclones, floods and volcanoes. They are NOT official Philippine warnings.
Data: CC BY 4.0, reuse allowed with credit to GDACS. Feed: https://www.gdacs.org/xml/rss.xml"""
import sqlite3

from .. import config
from ..timeutil import iso, utc_now
from .text import clean_text, clean_url, fetch, parse_date, safe_xml

NAME = "gdacs"
NS = {"gdacs": "http://www.gdacs.org", "georss": "http://www.georss.org/georss",
      "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#"}
CATEGORY = {"TC": "tropical_cyclone", "FL": "flood", "VO": "volcano"}
LEVELS = {"red": "Red", "orange": "Orange", "green": "Green"}


def _t(item, tag):
    el = item.find(tag, NS)
    return el.text.strip() if el is not None and el.text and el.text.strip() else None


def _point(item):
    """(lat, lng) from <georss:point>lat lon</georss:point>, falling back to <geo:Point>."""
    raw = _t(item, "georss:point")
    try:
        if raw:
            lat, lng = (float(x) for x in raw.split()[:2])
            return lat, lng
        return float(_t(item, "geo:Point/geo:lat")), float(_t(item, "geo:Point/geo:long"))
    except (TypeError, ValueError):
        return None, None


def _near_philippines(country: str, lat, lng) -> bool:
    if "philippines" in country.lower():
        return True
    if lat is None or lng is None:
        return False
    min_lat, max_lat, min_lng, max_lng = config.GDACS_NEAR_BOX
    return min_lat <= lat <= max_lat and min_lng <= lng <= max_lng


def parse_feed(xml_text: str) -> tuple[int, list[dict]]:
    """(events in the whole feed, current events that concern the Philippines)."""
    root = safe_xml(xml_text)
    total, out = 0, []
    for item in root.iter("item"):
        etype, event_id = _t(item, "gdacs:eventtype"), _t(item, "gdacs:eventid")
        if not etype or not event_id:
            continue
        total += 1
        if etype not in config.GDACS_TYPES or (_t(item, "gdacs:iscurrent") or "").lower() != "true":
            continue
        country = clean_text(_t(item, "gdacs:country") or "", 120)
        lat, lng = _point(item)
        if not _near_philippines(country, lat, lng):
            continue
        out.append({
            "ext_id": f"gdacs:{etype}:{event_id}",            # one row per event, updated as new episodes arrive
            "source": "GDACS",
            "title": clean_text(_t(item, "title") or f"GDACS {etype} alert", 200),
            "body": clean_text(_t(item, "description"), 450),
            "severity": LEVELS.get((_t(item, "gdacs:alertlevel") or "").lower(), "Green"),
            "category": CATEGORY[etype],
            "area": country or None,
            "issued_at": parse_date(_t(item, "gdacs:datemodified") or _t(item, "pubDate")),
            "expires_at": parse_date(_t(item, "gdacs:todate")),
            "url": clean_url(_t(item, "link")),
            "lat": lat, "lng": lng,
        })
    return total, out


def refresh(conn: sqlite3.Connection, client, now=None) -> dict:
    now_iso = iso(now or utc_now())
    total, events = parse_feed(fetch(client, config.GDACS_URL).text)
    if total == 0:
        # The global feed always lists events somewhere. An empty one means the format changed,
        # and treating that as "no alerts" would delete real ones.
        raise ValueError("the feed had no events (format changed?)")
    for e in events:
        conn.execute(
            """INSERT INTO advisories (ext_id,source,title,body,severity,category,area,issued_at,expires_at,url,lat,lng,fetched_at)
               VALUES (:ext_id,:source,:title,:body,:severity,:category,:area,:issued_at,:expires_at,:url,:lat,:lng,:now)
               ON CONFLICT(ext_id) DO UPDATE SET title=excluded.title, body=excluded.body, severity=excluded.severity,
                 category=excluded.category, area=excluded.area, issued_at=excluded.issued_at,
                 expires_at=excluded.expires_at, url=excluded.url, lat=excluded.lat, lng=excluded.lng,
                 fetched_at=excluded.fetched_at""",
            {**e, "now": now_iso},
        )
    # Events that are no longer current disappear from the feed. A successful read means they are over.
    keep = [e["ext_id"] for e in events]
    marks = ",".join("?" * len(keep)) or "''"
    conn.execute(f"DELETE FROM advisories WHERE source = 'GDACS' AND ext_id NOT IN ({marks})", keep)
    conn.commit()
    return {"saved": len(events), "errors": []}
