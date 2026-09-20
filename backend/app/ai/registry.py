import logging
from typing import Type, TypeVar, Optional, Any

from .interfaces import (
    TextClassifier,
    ImageAnalyzer,
    EmbeddingProvider,
    DuplicateDetector,
    AnomalyDetector,
    TrustAssessor
)

log = logging.getLogger("indra.ai.registry")

T = TypeVar("T")

class AIRegistry:
    """
    Central registry for resolving AI/ML providers. 
    Allows interchangeable models based on configuration, enabling
    easy swapping between rule-based, local ML, or API-based providers.
    """
    def __init__(self):
        self._providers = {}
        self._active_providers = {}

    def register(self, interface: Type[T], name: str, provider_instance: T, is_default: bool = False):
        if interface not in self._providers:
            self._providers[interface] = {}
        self._providers[interface][name] = provider_instance
        
        if is_default or interface not in self._active_providers:
            self.set_active(interface, name)

    def set_active(self, interface: Type[T], name: str):
        if interface in self._providers and name in self._providers[interface]:
            self._active_providers[interface] = self._providers[interface][name]
            log.info(f"Set active provider for {interface.__name__} to '{name}'.")
        else:
            raise ValueError(f"Provider '{name}' for interface {interface.__name__} not found.")

    def get(self, interface: Type[T]) -> T:
        provider = self._active_providers.get(interface)
        if not provider:
            raise ValueError(f"No active provider found for {interface.__name__}")
        return provider

# Global registry instance
registry = AIRegistry()

# Helper function to get capabilities easily
def get_text_classifier() -> TextClassifier:
    return registry.get(TextClassifier)

def get_image_analyzer() -> ImageAnalyzer:
    return registry.get(ImageAnalyzer)

def get_embedding_provider() -> EmbeddingProvider:
    return registry.get(EmbeddingProvider)

def get_duplicate_detector() -> DuplicateDetector:
    return registry.get(DuplicateDetector)

def get_anomaly_detector() -> AnomalyDetector:
    return registry.get(AnomalyDetector)

def get_trust_assessor() -> TrustAssessor:
    return registry.get(TrustAssessor)
