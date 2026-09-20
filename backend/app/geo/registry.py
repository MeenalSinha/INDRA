import logging
from typing import Optional
from .interfaces import IGeocoder, ISpatialStore
from ..core import config

log = logging.getLogger("indra.geo.registry")

class GeoRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GeoRegistry, cls).__new__(cls)
            cls._instance.geocoder = None
            cls._instance.spatial_store = None
        return cls._instance

    def set_geocoder(self, provider: IGeocoder):
        self.geocoder = provider

    def get_geocoder(self) -> IGeocoder:
        if not self.geocoder:
            raise RuntimeError("Geocoder provider not initialized")
        return self.geocoder

    def set_spatial_store(self, provider: ISpatialStore):
        self.spatial_store = provider

    def get_spatial_store(self) -> ISpatialStore:
        if not self.spatial_store:
            raise RuntimeError("SpatialStore provider not initialized")
        return self.spatial_store


def get_geocoder() -> IGeocoder:
    return GeoRegistry().get_geocoder()

def get_spatial_store() -> ISpatialStore:
    return GeoRegistry().get_spatial_store()


def init_geo_providers():
    """Initializes the active providers based on the current configuration."""
    registry = GeoRegistry()

    # Geocoder
    from .providers.geocoder import NominatimGeocoder, StubGeocoder
    # In live mode (or always, since it falls back) we can use Nominatim
    registry.set_geocoder(NominatimGeocoder())
    log.info("Registered Geocoder: NominatimGeocoder")

    # Spatial Store
    if config.IS_POSTGRES:
        from .providers.spatial import PostgisSpatialStore
        registry.set_spatial_store(PostgisSpatialStore())
        log.info("Registered SpatialStore: PostgisSpatialStore")
    else:
        from .providers.spatial import FallbackSpatialStore
        registry.set_spatial_store(FallbackSpatialStore())
        log.info("Registered SpatialStore: FallbackSpatialStore")
