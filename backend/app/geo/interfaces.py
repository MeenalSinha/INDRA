from abc import ABC, abstractmethod
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session

class IGeocoder(ABC):
    """Abstract Base Class for Geocoding services."""
    @abstractmethod
    async def geocode(self, city: str, state: str = "") -> Optional[Tuple[float, float]]:
        """Geocodes a city/state into latitude and longitude."""
        pass


class ISpatialStore(ABC):
    """Abstract Base Class for Spatial Storage operations."""
    @abstractmethod
    def sync_report_geom(self, db: Session, report_id: int, lat: float, lng: float) -> None:
        """Syncs the geometry for a report (no-op if not supported)."""
        pass

    @abstractmethod
    def sync_event_geom(self, db: Session, event_id: int, lat: float, lng: float) -> None:
        """Syncs the geometry for an event (no-op if not supported)."""
        pass

    @abstractmethod
    def events_within_radius(self, db: Session, lat: float, lng: float, radius_km: float) -> tuple[int, List["models.Event"]]: # type: ignore
        """Returns the number and list of events within the given radius."""
        pass
