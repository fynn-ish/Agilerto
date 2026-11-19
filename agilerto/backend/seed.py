"""Load the permanent (static) data into SQLite.
"""
import argparse
import csv
from pathlib import Path

from app.chunks import rebuild_static_chunks
from app.db import DB_PATH, connect, init_db

DATA = Path(__file__).parent / "data"


def read_csv(name: str):
    with open(DATA / name, newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def num(v, cast=float):
    return cast(v) if v not in (None, "") else None


def seed(conn):
    for r in read_csv("facilities.csv"):
        conn.execute(
            """INSERT INTO facilities (ref,type,name,lat,lng,address,phone,capacity,source,verified)
               VALUES (:ref,:type,:name,:lat,:lng,:address,:phone,:capacity,:source,:verified)
               ON CONFLICT(ref) DO UPDATE SET type=excluded.type, name=excluded.name,
                 lat=excluded.lat, lng=excluded.lng, address=excluded.address, phone=excluded.phone,
                 capacity=excluded.capacity, source=excluded.source, verified=excluded.verified,
                 updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')""",
            {**r, "lat": float(r["lat"]), "lng": float(r["lng"]),
             "capacity": num(r["capacity"], int), "phone": r["phone"] or None,
             "verified": int(r["verified"])},
        )
    for r in read_csv("emergency_numbers.csv"):
        conn.execute(
            """INSERT INTO emergency_numbers (ref,agency,number,area,notes,priority,source,verified)
               VALUES (:ref,:agency,:number,:area,:notes,:priority,:source,:verified)
               ON CONFLICT(ref) DO UPDATE SET agency=excluded.agency, number=excluded.number,
                 area=excluded.area, notes=excluded.notes, priority=excluded.priority,
                 source=excluded.source, verified=excluded.verified""",
            {**r, "priority": int(r["priority"]), "verified": int(r["verified"])},
        )
    for r in read_csv("safety_guides.csv"):
        conn.execute(
            """INSERT INTO safety_guides (ref,hazard,phase,title,body,source,verified)
               VALUES (:ref,:hazard,:phase,:title,:body,:source,:verified)
               ON CONFLICT(ref) DO UPDATE SET hazard=excluded.hazard, phase=excluded.phase,
                 title=excluded.title, body=excluded.body, source=excluded.source,
                 verified=excluded.verified""",
            {**r, "verified": int(r["verified"])},
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="delete the database before seeding")
    args = ap.parse_args()

    if args.reset and DB_PATH.exists():
        for suffix in ("", "-wal", "-shm"):
            Path(str(DB_PATH) + suffix).unlink(missing_ok=True)
        print(f"Deleted {DB_PATH}")

    init_db()
    conn = connect()
    try:
        with conn:                      # single transaction
            seed(conn)
            counts = rebuild_static_chunks(conn)
        print(f"Seeded {DB_PATH}")
        for t in ("facilities", "emergency_numbers", "safety_guides", "chunks"):
            print(f"  {t:18} {conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}")
        print(f"  chunks built: {counts}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
