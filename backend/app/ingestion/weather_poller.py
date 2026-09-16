"""
§5 Real external source adapter — OpenWeatherMap free tier.

Polls the OpenWeatherMap Current Weather API for a configured list of
Indian cities and ingests the results through the existing ingest_report()
pipeline — not a parallel path.

Activation: set OWM_API_KEY env var to your free-tier key from
https://openweathermap.org/api (no credit card required for free tier).
If OWM_API_KEY is unset, the poller stays completely dormant and has
zero effect on Demo Mode.

Poll interval: OWM_POLL_INTERVAL_SECONDS (default 600 = 10 min).
City list: OWM_CITIES (comma-separated, default: major Indian cities).

The poller runs as a FastAPI background task started at app startup
(wired in main.py). No threads are created — uses asyncio.sleep().

Social media / IMD API: intentionally NOT implemented. See LIMITATIONS.md:
  - Social platform APIs prohibit automated access without the account
    holder's own credentials + ToS compliance.
  - IMD's machine-readable open data portal URL was unreachable at test
    time (HTTP 503); not simulated.
"""
import asyncio
import datetime as dt
import logging
import os

import httpx

log = logging.getLogger("indra.ingestion.weather_poller")

OWM_API_KEY = os.getenv("OWM_API_KEY", "")
OWM_POLL_INTERVAL = int(os.getenv("OWM_POLL_INTERVAL_SECONDS", "600"))
_DEFAULT_CITIES = (
    "Patna,IN Guwahati,IN Mumbai,IN Delhi,IN Chennai,IN Jaipur,IN "
    "Bengaluru,IN Hyderabad,IN Kolkata,IN Ahmedabad,IN Bhubaneswar,IN"
)
OWM_CITIES = [
    c.strip() for c in os.getenv("OWM_CITIES", _DEFAULT_CITIES).split()
    if c.strip()
]

_OWM_BASE = "https://api.openweathermap.org/data/2.5/weather"

# Map OWM weather main category → INDRA event type
_OWM_TO_EVENT_TYPE = {
    "Thunderstorm": "Thunderstorm",
    "Drizzle":      "Heavy Rainfall",
    "Rain":         "Heavy Rainfall",
    "Snow":         "Other",
    "Mist":         "Fog",
    "Smoke":        "Dust Storm",
    "Haze":         "Dust Storm",
    "Dust":         "Dust Storm",
    "Fog":          "Fog",
    "Sand":         "Dust Storm",
    "Ash":          "Other",
    "Squall":       "Strong Winds",
    "Tornado":      "Strong Winds",
    "Clear":        None,   # not a weather event
    "Clouds":       None,
}


def _owm_to_report(data: dict) -> dict | None:
    """Convert an OWM API response dict to an INDRA ingest_report() payload.
    Returns None for non-event conditions (clear/cloudy)."""
    weather = data.get("weather", [{}])[0]
    main = weather.get("main", "")
    event_type = _OWM_TO_EVENT_TYPE.get(main)
    if event_type is None:
        return None  # Clear/Clouds — not worth ingesting

    city = data.get("name", "")
    sys = data.get("sys", {})
    country = sys.get("country", "")
    coord = data.get("coord", {})
    wind_speed_ms = data.get("wind", {}).get("speed", 0)
    rain_1h = data.get("rain", {}).get("1h", 0.0)
    desc = weather.get("description", "").capitalize()
    temp_c = data.get("main", {}).get("temp", 0) - 273.15  # Kelvin → C

    text = (
        f"[OWM] {desc} in {city}. "
        f"Wind: {round(wind_speed_ms * 3.6)} km/h. "
        f"Temp: {round(temp_c, 1)}°C."
    )
    if rain_1h:
        text += f" Rain last 1h: {rain_1h} mm."

    return {
        "source": "OpenWeatherMap",
        "source_type": "weather_api",
        "text": text,
        "timestamp": dt.datetime.utcnow().isoformat(),
        "latitude": coord.get("lat"),
        "longitude": coord.get("lon"),
        "city": city,
        "state": "",       # OWM doesn't return state; geocoder fills if city matches
        "hashtags": [f"#{main}", "#OWM"],
        "raw_metadata": {
            "owm_id": data.get("id"),
            "weather_main": main,
            "wind_speed_ms": wind_speed_ms,
            "rain_1h_mm": rain_1h,
            "temp_c": round(temp_c, 1),
        },
    }


from .adapters import WeatherAPIAdapter

class OWMAdapter(WeatherAPIAdapter):
    """Implementation of WeatherAPIAdapter for OpenWeatherMap."""
    def __init__(self):
        self.api_key = OWM_API_KEY
        self.cities = OWM_CITIES
        self.base_url = _OWM_BASE

    def fetch(self) -> list[dict]:
        raise NotImplementedError("Use async_fetch for OWM API")
        
    async def async_fetch(self) -> list[dict]:
        reports = []
        async with httpx.AsyncClient(timeout=10) as client:
            for city_q in self.cities:
                try:
                    resp = await client.get(
                        self.base_url,
                        params={"q": city_q, "appid": self.api_key},
                    )
                    if resp.status_code != 200:
                        log.debug("OWM %s → HTTP %s", city_q, resp.status_code)
                        continue
                    data = resp.json()
                    payload = _owm_to_report(data)
                    if payload:
                        reports.append(payload)
                except Exception as exc:
                    log.warning("OWM poll error for %s: %s", city_q, exc)
        return reports
        
    async def poll(self, db_session_factory):
        raw_reports = await self.async_fetch()
        for raw in raw_reports:
            payload = self.normalize(raw)
            if self.validate(payload):
                db = db_session_factory()
                try:
                    await self.publish(db, payload)
                    log.info("OWM ingested: %s → %s", payload.get("city"), payload["text"][:80])
                finally:
                    db.close()


async def run_weather_poller(db_session_factory):
    """Background coroutine. Runs indefinitely while the app is up.
    Starts only if OWM_API_KEY is set — completely dormant otherwise."""
    if not OWM_API_KEY:
        log.info("OWM_API_KEY not set — weather poller dormant (Demo Mode).")
        return

    log.info(
        "OpenWeatherMap poller active: %d cities, interval %ds.",
        len(OWM_CITIES), OWM_POLL_INTERVAL,
    )
    adapter = OWMAdapter()
    while True:
        try:
            await adapter.poll(db_session_factory)
        except Exception as exc:
            log.error("OWM poll cycle failed: %s", exc)
        await asyncio.sleep(OWM_POLL_INTERVAL)
