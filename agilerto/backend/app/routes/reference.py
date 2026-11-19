"""Static reference data: hotlines and safety guides. Always available offline."""
from typing import Optional

from fastapi import APIRouter, Depends

from ..db import get_db

router = APIRouter()


@router.get("/emergency-numbers")
def emergency_numbers(db=Depends(get_db)):
    rows = db.execute(
        "SELECT agency, number, area, notes, source, verified "
        "FROM emergency_numbers ORDER BY priority, agency"
    ).fetchall()
    return {"count": len(rows), "numbers": [dict(r) for r in rows]}


@router.get("/safety-guides")
def safety_guides(hazard: Optional[str] = None, db=Depends(get_db)):
    sql = "SELECT hazard, phase, title, body, source, verified FROM safety_guides"
    params = []
    if hazard:
        sql += " WHERE hazard = ?"
        params.append(hazard)
    sql += " ORDER BY hazard, CASE phase WHEN 'before' THEN 1 WHEN 'during' THEN 2 ELSE 3 END"
    rows = db.execute(sql, params).fetchall()
    return {"count": len(rows), "guides": [dict(r) for r in rows]}


@router.get("/health")
def health(db=Depends(get_db)):
    counts = {
        t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("facilities", "emergency_numbers", "safety_guides")
    }
    return {"status": "ok", "counts": counts}
