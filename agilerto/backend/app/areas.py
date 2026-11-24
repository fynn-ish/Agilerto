"""Which monitored city is nearest to a location (used to find local news)."""
from . import config
from .geo import haversine_km


def nearest_area(lat: float, lng: float, max_km: float = 60.0):
    best = min(config.AREAS, key=lambda a: haversine_km(lat, lng, a["lat"], a["lng"]))
    return best if haversine_km(lat, lng, best["lat"], best["lng"]) <= max_km else None


def local_tags(lat: float, lng: float) -> set[str]:
    """Place tags that count as 'local' for this location, e.g. {'batangas', 'calabarzon'}."""
    area = nearest_area(lat, lng)
    if not area:
        return set()
    return {area["province"].lower(), "calabarzon"}
