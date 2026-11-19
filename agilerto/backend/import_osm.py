"""Import real facilities from OpenStreetMap 
"""
import argparse

import httpx

from app.chunks import rebuild_static_chunks
from app.db import connect, init_db

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_BBOX = "13.80,121.05,14.20,121.35"   # south,west,north,east

# (OSM tag, value) -> our facility type
TAG_MAP = [
    (("amenity", "hospital"), "hospital"),
    (("amenity", "fire_station"), "fire_station"),
    (("amenity", "police"), "police_station"),
    (("emergency", "assembly_point"), "evacuation_center"),
    (("amenity", "shelter"), "evacuation_center"),
]


def build_query(bbox: str) -> str:
    parts = []
    for (k, v), _ in TAG_MAP:
        for el in ("node", "way", "relation"):
            parts.append(f'{el}["{k}"="{v}"]({bbox});')
    return "[out:json][timeout:60];(" + "".join(parts) + ");out center tags;"


def classify(tags: dict):
    for (k, v), ftype in TAG_MAP:
        if tags.get(k) == v:
            return ftype
    return None


def parse_elements(elements: list) -> list:
    rows = []
    for el in elements:
        tags = el.get("tags", {})
        ftype = classify(tags)
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lng = el.get("lon") or (el.get("center") or {}).get("lon")
        if not ftype or lat is None or lng is None:
            continue
        addr = ", ".join(filter(None, [
            tags.get("addr:housenumber"), tags.get("addr:street"),
            tags.get("addr:suburb") or tags.get("addr:barangay"),
            tags.get("addr:city") or tags.get("addr:municipality"),
        ])) or None
        rows.append({
            "ref": f"osm:{el['type']}/{el['id']}",
            "type": ftype,
            "name": tags.get("name") or tags.get("name:en") or f"Unnamed {ftype.replace('_', ' ')}",
            "lat": lat, "lng": lng, "address": addr,
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "capacity": int(tags["capacity"]) if str(tags.get("capacity", "")).isdigit() else None,
            "source": "OpenStreetMap (ODbL)",
        })
    return rows


def save(conn, rows: list, replace_samples: bool):
    with conn:
        if replace_samples and rows:
            conn.execute("DELETE FROM facilities WHERE ref LIKE 'seed:%'")
        for r in rows:
            conn.execute(
                """INSERT INTO facilities (ref,type,name,lat,lng,address,phone,capacity,source,verified)
                   VALUES (:ref,:type,:name,:lat,:lng,:address,:phone,:capacity,:source,0)
                   ON CONFLICT(ref) DO UPDATE SET name=excluded.name, lat=excluded.lat, lng=excluded.lng,
                     address=excluded.address, phone=excluded.phone, capacity=excluded.capacity,
                     updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')""",
                r,
            )
        rebuild_static_chunks(conn)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", default=DEFAULT_BBOX, help="south,west,north,east")
    ap.add_argument("--replace-samples", action="store_true")
    args = ap.parse_args()

    print(f"Querying Overpass for bbox {args.bbox} ...")
    resp = httpx.post(OVERPASS_URL, data={"data": build_query(args.bbox)}, timeout=90)
    resp.raise_for_status()
    rows = parse_elements(resp.json().get("elements", []))

    init_db()
    conn = connect()
    try:
        save(conn, rows, args.replace_samples)
    finally:
        conn.close()
    by_type = {}
    for r in rows:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
    print(f"Imported {len(rows)} facilities: {by_type}")


if __name__ == "__main__":
    main()
