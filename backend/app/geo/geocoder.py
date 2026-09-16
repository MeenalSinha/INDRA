import logging
import httpx
from typing import Optional, Tuple
from functools import lru_cache

log = logging.getLogger("indra.geo.geocoder")

# In-memory simple cache. In production, we'd use Redis per Phase 23.
# We limit to 1024 distinct locations for memory safety.
@lru_cache(maxsize=1024)
def _geocode_cached(city: str, state: str) -> Optional[Tuple[float, float]]:
    """
    Offline dictionary for Demo mode or cache for Live mode.
    """
    query = f"{city} {state}".strip().lower()
    
    # Offline dictionary to ensure golden path scenarios work without network
    OFFLINE_LOCATIONS = {
        "patna bihar": (25.5941, 85.1376),
        "patna": (25.5941, 85.1376),
        "mumbai maharashtra": (19.0760, 72.8777),
        "mumbai": (19.0760, 72.8777),
        "chennai tamil nadu": (13.0827, 80.2707),
        "chennai": (13.0827, 80.2707),
        "guwahati assam": (26.1445, 91.7362),
        "guwahati": (26.1445, 91.7362),
    }
    
    if query in OFFLINE_LOCATIONS:
        return OFFLINE_LOCATIONS[query]
        
    return None

async def geocode(city: str, state: str = "") -> Optional[Tuple[float, float]]:
    """
    Configurable geocoder with caching (Phase 12).
    Uses offline dictionary first (cache), then falls back to public API if needed.
    """
    cached = _geocode_cached(city, state)
    if cached:
        return cached
        
    query = f"{city},{state},India" if state else f"{city},India"
    
    # Fallback to an external geocoder (Nominatim OpenStreetMap)
    # Be aware of rate limits.
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "limit": 1},
                headers={"User-Agent": "INDRA_Project_Prototype/1.0"}
            )
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    lat = float(data[0]["lat"])
                    lon = float(data[0]["lon"])
                    # Manually populate cache
                    _geocode_cached.cache_info() # purely informational, we can't easily push to lru_cache
                    return lat, lon
    except Exception as exc:
        log.warning("Geocoding failed for %s: %s", query, exc)
        
    return None
