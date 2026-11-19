"""Distance helpers. No PostGIS needed: bounding box in SQL, haversine in Python."""
import math

EARTH_RADIUS_KM = 6371.0088
KM_PER_DEG_LAT = 111.32


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def bounding_box(lat: float, lng: float, radius_km: float):
    """(min_lat, max_lat, min_lng, max_lng) that fully contains the search circle."""
    dlat = radius_km / KM_PER_DEG_LAT
    # longitude degrees shrink toward the poles; clamp to avoid division by ~0
    dlng = radius_km / (KM_PER_DEG_LAT * max(math.cos(math.radians(lat)), 0.01))
    return lat - dlat, lat + dlat, lng - dlng, lng + dlng
