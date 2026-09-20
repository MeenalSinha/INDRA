import logging
from typing import List, Dict
from sqlalchemy import text
from ..core import config
from ..geo.utils import haversine_km

log = logging.getLogger("indra.geo.risk_zones")

# Offline default risk zones for Demo Mode (Phase 17)
_DEMO_RISK_ZONES = [
    {"id": 1, "name": "Patna Flood Plain", "zone_type": "Flood", "risk_level": "CRITICAL", "lat": 25.59, "lon": 85.13, "radius_km": 15},
    {"id": 2, "name": "Mumbai Coastal Zone", "zone_type": "Cyclone", "risk_level": "HIGH", "lat": 19.07, "lon": 72.87, "radius_km": 20},
    {"id": 3, "name": "Guwahati Lowlands", "zone_type": "Flood", "risk_level": "HIGH", "lat": 26.14, "lon": 91.73, "radius_km": 10},
]

def get_risk_zones(db) -> List[Dict]:
    """Retrieve configured risk zones. Uses DB if Postgres, else offline defaults."""
    if config.IS_POSTGRES:
        try:
            # Query risk zones from DB (assuming a risk_zones table is created in Phase 22)
            rows = db.execute(text("SELECT id, name, zone_type, risk_level, ST_Y(geom) as lat, ST_X(geom) as lon, radius_km FROM risk_zones")).fetchall()
            return [{"id": r[0], "name": r[1], "zone_type": r[2], "risk_level": r[3], "lat": r[4], "lon": r[5], "radius_km": r[6]} for r in rows]
        except Exception as exc:
            log.warning("Failed to query risk_zones from DB, falling back to defaults: %s", exc)
            
    return _DEMO_RISK_ZONES

def check_intersection(lat: float, lon: float, zones: List[Dict]) -> List[Dict]:
    """Return risk zones intersecting with the given coordinates."""
    intersecting = []
    if lat is None or lon is None:
        return intersecting
        
    for z in zones:
        dist = haversine_km(lat, lon, z["lat"], z["lon"])
        if dist <= z["radius_km"]:
            intersecting.append(z)
            
    return intersecting

