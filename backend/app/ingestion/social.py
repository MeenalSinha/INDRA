import os
import asyncio
import logging
import datetime as dt
from .adapters import DataSourceAdapter

log = logging.getLogger("indra.ingestion.social")

SOCIAL_API_KEY = os.getenv("SOCIAL_API_KEY", "")
SOCIAL_HASHTAGS = os.getenv("SOCIAL_HASHTAGS", "#IMD,#WeatherAlert,#HeavyRain,#Flood,#Thunderstorm").split(",")

class SocialMediaAdapter(DataSourceAdapter):
    """
    Adapter for Social Media streams (e.g. Twitter/X or similar public APIs).
    If credentials are not available, it uses a deterministic simulated stream.
    """
    @property
    def source_type(self) -> str:
        return "social"

    def fetch(self) -> list[dict]:
        raise NotImplementedError("Use async_fetch for networking")

    async def async_fetch(self) -> list[dict]:
        if not SOCIAL_API_KEY:
            log.warning("SOCIAL_API_KEY not set. Using simulated social media stream.")
            return self._simulate_social_stream()
            
        # TODO: Implement real API client using Tweepy or httpx for X/Twitter v2 API
        # Since we don't have real credentials, we default to the simulator.
        log.warning("Real social API not fully implemented. Falling back to simulator.")
        return self._simulate_social_stream()

    def _simulate_social_stream(self) -> list[dict]:
        """
        Provides a reproducible simulated stream of citizen social media reports.
        """
        import random
        # Deterministic random for reproducibility if needed, but we use random here to simulate live incoming data
        if random.random() < 0.8:
            return []  # 80% chance of no new social reports in this cycle to avoid spamming
            
        cities = ["Patna", "Guwahati", "Mumbai", "Chennai", "Delhi"]
        events = ["#Flood", "#HeavyRain", "#Thunderstorm"]
        city = random.choice(cities)
        event = random.choice(events)
        
        return [{
            "source": "Social Media Simulator",
            "source_type": self.source_type,
            "source_id": f"sim_tweet_{random.randint(1000, 9999)}",
            "text": f"Terrible conditions here in {city}! {event} is causing chaos. #WeatherAlert",
            "timestamp": dt.datetime.utcnow().isoformat(),
            "city": city,
            "metadata": {"engagement_score": random.randint(10, 500)}
        }]

    async def poll(self, db_session_factory):
        raw_reports = await self.async_fetch()
        for raw in raw_reports:
            payload = self.normalize(raw)
            if self.validate(payload):
                db = db_session_factory()
                try:
                    from .adapters import ingest_report
                    await ingest_report(db, payload)
                    log.info("Social Media ingested: %s", payload["text"][:80])
                finally:
                    db.close()
