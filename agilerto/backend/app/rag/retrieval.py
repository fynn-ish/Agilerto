"""RAG retrieval. Finds the few saved records that can answer a question:
  1. intent routing (facilities by distance, nearest weather, nearby recent quakes, hotlines, safety guides)
  2. FTS5 keyword search to fill any remaining slots
Everything is read from SQLite, so it works offline."""
import re
from dataclasses import dataclass, field

from .. import config
from ..geo import bounding_box, haversine_km
from ..timeutil import utc_now
from . import intents as I


@dataclass
class Source:
    kind: str                      # facility | hotline | guide | weather | quake
    ref_id: str
    title: str
    text: str
    source: str | None = None
    as_of: str | None = None       # fetched_at for live data; None = saved reference data
    lat: float | None = None
    lng: float | None = None
    distance_km: float | None = None
    verified: bool | None = None
    facility: dict | None = None
    n: int = 0
    extra: dict = field(default_factory=dict)


class _Picker:
    def __init__(self, limit: int):
        self.limit, self.items, self.seen = limit, [], set()

    def add(self, s: Source) -> bool:
        key = (s.kind, s.ref_id)
        if key in self.seen or len(self.items) >= self.limit:
            return False
        s.text = s.text[: config.SOURCE_MAX_CHARS]
        self.seen.add(key)
        self.items.append(s)
        return True

    @property
    def free(self) -> int:
        return self.limit - len(self.items)


def _facility_source(row, chunk_text: str, dist: float) -> Source:
    fac = {k: row[k] for k in ("id", "type", "name", "lat", "lng", "address", "phone", "capacity", "source")}
    fac["verified"] = bool(row["verified"])
    fac["distance_km"] = round(dist, 2)
    return Source(
        kind="facility", ref_id=row["ref"], title=row["name"],
        text=f"{chunk_text} Distance from you: {dist:.2f} km.", source=row["source"],
        lat=row["lat"], lng=row["lng"], distance_km=round(dist, 2), verified=bool(row["verified"]), facility=fac,
    )


def nearest_facilities(conn, lat, lng, types, per_type, radius=config.FACILITY_RADIUS_KM) -> list[Source]:
    min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius)
    marks = ",".join("?" * len(types))
    rows = conn.execute(
        f"""SELECT f.*, c.text AS chunk_text FROM facilities f
            JOIN chunks c ON c.kind = 'facility' AND c.ref_id = f.ref
            WHERE f.lat BETWEEN ? AND ? AND f.lng BETWEEN ? AND ? AND f.type IN ({marks})""",
        [min_lat, max_lat, min_lng, max_lng, *types],
    ).fetchall()
    scored = sorted(((haversine_km(lat, lng, r["lat"], r["lng"]), r) for r in rows), key=lambda x: x[0])
    out, count = [], {t: 0 for t in types}
    for d, r in scored:
        if d <= radius and count[r["type"]] < per_type:
            out.append(_facility_source(r, r["chunk_text"], d))
            count[r["type"]] += 1
    return out


def nearest_weather(conn, lat, lng) -> Source | None:
    best = None
    for r in conn.execute("SELECT * FROM chunks WHERE kind = 'weather'"):
        if r["lat"] is None:
            continue
        d = haversine_km(lat, lng, r["lat"], r["lng"])
        if d <= config.WEATHER_MAX_KM and (best is None or d < best[0]):
            best = (d, r)
    if not best:
        return None
    d, r = best
    return Source(kind="weather", ref_id=r["ref_id"], title=r["title"], source=r["source"], as_of=r["fetched_at"],
                  text=f"{r['text']} (Saved for {r['ref_id']}, {d:.0f} km from you.)", lat=r["lat"], lng=r["lng"],
                  distance_km=round(d, 1))


def recent_quakes(conn, lat, lng, limit=4, days=7) -> list[Source]:
    from datetime import timedelta
    from ..timeutil import iso
    cutoff = iso(utc_now() - timedelta(days=days))
    rows = conn.execute(
        """SELECT c.*, e.occurred_at FROM chunks c JOIN earthquakes e ON e.ext_id = c.ref_id
           WHERE c.kind = 'quake' AND e.occurred_at >= ?""", (cutoff,)).fetchall()
    near = []
    for r in rows:
        d = haversine_km(lat, lng, r["lat"], r["lng"])
        if d <= config.QUAKE_RADIUS_KM:
            near.append((r["occurred_at"], d, r))
    near.sort(key=lambda x: x[0], reverse=True)
    return [Source(kind="quake", ref_id=r["ref_id"], title=r["title"], source=r["source"], as_of=r["fetched_at"],
                   text=f"{r['text']} Distance from you: {d:.0f} km.", lat=r["lat"], lng=r["lng"],
                   distance_km=round(d)) for _, d, r in near[:limit]]


def hotlines(conn) -> list[Source]:
    out = []
    for r in conn.execute(
        "SELECT c.*, e.priority FROM chunks c JOIN emergency_numbers e ON e.ref = c.ref_id "
        "WHERE c.kind = 'hotline' ORDER BY e.priority"):
        if re.search(r"\d", r["text"]):                      # skip placeholder rows like "ADD LOCAL NUMBER"
            out.append(Source(kind="hotline", ref_id=r["ref_id"], title=r["title"], text=r["text"], source=r["source"]))
    return out


def guides(conn, hazards, phase=None, per_hazard=3) -> list[Source]:
    order = {"during": 1, "before": 2, "after": 3}
    if phase:
        order[phase] = 0
    out = []
    for hz in hazards:
        rows = conn.execute(
            "SELECT c.*, g.phase FROM chunks c JOIN safety_guides g ON g.ref = c.ref_id "
            "WHERE c.kind = 'guide' AND g.hazard = ?", (hz,)).fetchall()
        rows.sort(key=lambda r: order.get(r["phase"], 9))
        out += [Source(kind="guide", ref_id=r["ref_id"], title=r["title"], text=r["text"], source=r["source"])
                for r in rows[:per_hazard]]
    return out


def _fts_sources(conn, question, lat, lng, limit, skip_kinds=(), only_weather_ref=None) -> list[Source]:
    q = I.fts_query(question)
    if not q or limit <= 0:
        return []
    try:
        rows = conn.execute(
            """SELECT c.* FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid
               WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts, 4.0, 1.0) LIMIT 20""", (q,)).fetchall()
    except Exception:
        return []                                             # a malformed query must never break chat
    terms = re.findall(r'"([a-z0-9]+)"', q)
    need = 2 if len(terms) >= 3 else 1                      # a single weak word must not drag in unrelated records
    out = []
    for r in rows:
        kind, dist = r["kind"], None
        haystack = f"{r['title']} {r['text']}".lower()
        if sum(1 for t in terms if t in haystack) < need:
            continue
        if kind in skip_kinds:
            continue                                          # an intent already supplied the best records of this kind
        if kind == "weather" and only_weather_ref and r["ref_id"] != only_weather_ref:
            continue                                          # only ever the nearest city's weather
        if kind in ("facility", "weather", "quake") and r["lat"] is not None:
            dist = haversine_km(lat, lng, r["lat"], r["lng"])
            limit_km = {"facility": config.FACILITY_RADIUS_KM, "weather": config.WEATHER_MAX_KM,
                        "quake": config.QUAKE_RADIUS_KM}[kind]
            if dist > limit_km:
                continue                                      # keep the answer about the user's area
        if kind == "facility":
            f = conn.execute("SELECT * FROM facilities WHERE ref = ?", (r["ref_id"],)).fetchone()
            if f:
                out.append(_facility_source(f, r["text"], dist))
            continue
        text = r["text"] + (f" Distance from you: {dist:.0f} km." if dist is not None else "")
        out.append(Source(kind=kind, ref_id=r["ref_id"], title=r["title"], text=text, source=r["source"],
                          as_of=r["fetched_at"], lat=r["lat"], lng=r["lng"],
                          distance_km=round(dist) if dist is not None else None))
    return out[:limit]


def retrieve(conn, question: str, lat: float, lng: float, max_sources: int = config.MAX_SOURCES) -> list[Source]:
    """Numbered sources (1..n) most relevant to the question, for the user's location."""
    it = I.detect(question)
    pick = _Picker(max_sources)

    if it.facility_types:
        per = 3 if len(it.facility_types) == 1 else 2
        for s in nearest_facilities(conn, lat, lng, it.facility_types, per):
            pick.add(s)
    elif it.nearby and not (it.weather or it.quake or it.hazards or it.hotline):
        # "what's near me?": the closest one or two of every kind
        for s in nearest_facilities(conn, lat, lng, list(("hospital", "evacuation_center", "fire_station", "police_station")), 1):
            pick.add(s)

    nearest_w = nearest_weather(conn, lat, lng)
    if it.weather and nearest_w:
        pick.add(nearest_w)
    if it.quake:
        for s in recent_quakes(conn, lat, lng):
            pick.add(s)
    if it.hotline:
        for s in hotlines(conn):
            pick.add(s)
    if it.hazards:
        # a "what is happening" question needs only the most relevant guide; a "what should I do" question needs them all
        live_question = (it.quake or it.weather) and not it.howto
        per = 1 if live_question else (3 if len(it.hazards) == 1 else 2)
        for s in guides(conn, it.hazards, it.phase, per_hazard=per):
            pick.add(s)

    # Keyword search is the fallback for questions no intent recognised. When an intent matched, the records above
    # are the answer and extra keyword hits would only add noise for a small model.
    if not it.matched:
        for s in _fts_sources(conn, question, lat, lng, max_sources, (), nearest_w.ref_id if nearest_w else None):
            pick.add(s)

    for i, s in enumerate(pick.items, 1):
        s.n = i
    return pick.items
