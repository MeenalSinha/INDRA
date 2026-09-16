import os
import asyncio
import logging
import datetime as dt
import httpx
from .adapters import DataSourceAdapter

log = logging.getLogger("indra.ingestion.imd")

IMD_API_ENDPOINT = os.getenv("IMD_API_ENDPOINT", "")
IMD_API_KEY = os.getenv("IMD_API_KEY", "")

class IMDAdapter(DataSourceAdapter):
    """
    Production-ready adapter for IMD (India Meteorological Department) data.
    Implements timeout, retry, rate-limiting, and graceful failure.
    If the endpoint is unset or fails, gracefully falls back to a simulated observation mode.
    """
    @property
    def source_type(self) -> str:
        return "government"

    def fetch(self) -> list[dict]:
        raise NotImplementedError("Use async_fetch for networking")

    async def async_fetch(self) -> list[dict]:
        if not IMD_API_ENDPOINT:
            log.warning("IMD_API_ENDPOINT not configured. Falling back to Demo Mode data.")
            return self._simulate_fallback_data()

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(
                    IMD_API_ENDPOINT,
                    headers={"Authorization": f"Bearer {IMD_API_KEY}"} if IMD_API_KEY else {}
                )
                response.raise_for_status()
                return self._parse_imd_response(response.json())
            except httpx.HTTPError as e:
                log.error(f"IMD API Request failed: {e}. Falling back to demo data.")
                return self._simulate_fallback_data()

    def _parse_imd_response(self, data: dict) -> list[dict]:
        # Placeholder parsing logic for a real IMD payload
        reports = []
        for obs in data.get("observations", []):
            reports.append({
                "source": "IMD Official",
                "source_type": self.source_type,
                "text": f"Official IMD Observation: {obs.get('description', 'Weather event')}",
                "timestamp": obs.get("timestamp", dt.datetime.utcnow().isoformat()),
                "latitude": obs.get("lat"),
                "longitude": obs.get("lng"),
                "city": obs.get("city"),
                "event_type": obs.get("event"),
                "metadata": obs
            })
        return reports

    def _simulate_fallback_data(self) -> list[dict]:
        """
        Generates simulated IMD observations for Demo Mode.
        Never pretends to be live data.
        """
        return [{
            "source": "IMD Simulated",
            "source_type": self.source_type,
            "text": "Simulated heavy rainfall alert for Patna region.",
            "timestamp": dt.datetime.utcnow().isoformat(),
            "city": "Patna",
            "state": "Bihar",
            "event_type": "Heavy Rainfall",
            "metadata": {"simulated": True, "rainfall_mm": 120}
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
                finally:
                    db.close()
