"""
Geo utilities. In LIVE MODE with Postgres+PostGIS, these haversine
computations can be replaced with ST_DistanceSphere / ST_DWithin queries on
a geography(Point,4326) column -- see models.py note. For DEMO MODE
(SQLite) we compute distance in Python, which is exact for point-to-point
haversine and fast at demo data volumes.
"""
import math


def haversine_km(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return float("inf")
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))
