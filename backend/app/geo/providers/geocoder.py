import logging
import httpx
from typing import Optional, Tuple
from ..interfaces import IGeocoder

log = logging.getLogger("indra.geo.geocoder")

class StubGeocoder(IGeocoder):
    """
    Offline dictionary for Demo mode.
    """
    def __init__(self):
        self.OFFLINE_LOCATIONS = {
            "patna bihar": (25.5941, 85.1376),
            "patna": (25.5941, 85.1376),
            "mumbai maharashtra": (19.0760, 72.8777),
            "mumbai": (19.0760, 72.8777),
            "chennai tamil nadu": (13.0827, 80.2707),
            "chennai": (13.0827, 80.2707),
            "guwahati assam": (26.1445, 91.7362),
            "guwahati": (26.1445, 91.7362),
        }

    async def geocode(self, city: str, state: str = "") -> Optional[Tuple[float, float]]:
        query = f"{city} {state}".strip().lower()
        return self.OFFLINE_LOCATIONS.get(query)


class NominatimGeocoder(IGeocoder):
    """
    Real geocoder with HTTPx. Falls back to StubGeocoder if it fails.
    """
    def __init__(self):
        self.fallback = StubGeocoder()
        self.cache = {}

    async def geocode(self, city: str, state: str = "") -> Optional[Tuple[float, float]]:
        # Use fallback as initial cache
        fallback_res = await self.fallback.geocode(city, state)
        if fallback_res:
            return fallback_res

        query = f"{city},{state},India" if state else f"{city},India"
        if query in self.cache:
            return self.cache[query]

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
                        self.cache[query] = (lat, lon)
                        return lat, lon
        except Exception as exc:
            log.warning("Geocoding failed for %s: %s", query, exc)
            
        return None
