from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import get_db
from ..geo import bounding_box, haversine_km

router = APIRouter()

FACILITY_TYPES = {"hospital", "evacuation_center", "fire_station", "police_station"}


@router.get("/facilities")
def nearby_facilities(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10, gt=0, le=100),
    type: Optional[str] = Query(None, description="Comma-separated: hospital,evacuation_center,fire_station,police_station"),
    limit: int = Query(100, ge=1, le=500),
    db=Depends(get_db),
):
    """Facilities within radius_km of (lat, lng), nearest first. Works fully offline."""
    types = None
    if type:
        types = {t.strip() for t in type.split(",") if t.strip()}
        bad = types - FACILITY_TYPES
        if bad:
            raise HTTPException(422, f"Unknown facility type(s): {', '.join(sorted(bad))}")

    min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_km)
    sql = ("SELECT id, type, name, lat, lng, address, phone, capacity, source, verified "
           "FROM facilities WHERE lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?")
    params: list = [min_lat, max_lat, min_lng, max_lng]
    if types:
        sql += f" AND type IN ({','.join('?' * len(types))})"
        params += sorted(types)

    results = []
    for row in db.execute(sql, params):
        d = haversine_km(lat, lng, row["lat"], row["lng"])
        if d <= radius_km:                       # bbox is square, so trim to the real circle
            item = dict(row)
            item["verified"] = bool(item["verified"])
            item["distance_km"] = round(d, 2)
            results.append(item)

    results.sort(key=lambda r: r["distance_km"])
    return {
        "center": {"lat": lat, "lng": lng},
        "radius_km": radius_km,
        "count": len(results[:limit]),
        "facilities": results[:limit],
    }
