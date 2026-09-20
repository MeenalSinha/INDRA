from abc import ABC, abstractmethod
from typing import Any, Optional
from .models import AIResult

class TextClassifier(ABC):
    @abstractmethod
    async def predict(self, text: str, hashtags: Optional[list[str]] = None) -> AIResult:
        pass

class ImageAnalyzer(ABC):
    @abstractmethod
    async def analyze(self, image_bytes: Optional[bytes], content_type: str) -> AIResult:
        pass

class EmbeddingProvider(ABC):
    @abstractmethod
    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        pass
        
    @abstractmethod
    async def pairwise_similarity(self, texts: list[str]) -> list[list[float]]:
        pass

class DuplicateDetector(ABC):
    @abstractmethod
    async def find_duplicates(self, reports: list[Any]) -> list[dict[str, Any]]:
        pass

class AnomalyDetector(ABC):
    @abstractmethod
    async def predict(self, value: float, baseline: float, historical_values: Optional[list[float]] = None) -> AIResult:
        pass

class TrustAssessor(ABC):
    @abstractmethod
    async def predict(
        self, 
        source_type: str, 
        verification_history_count: int, 
        metadata_completeness: float,
        cross_source_agreement: float = 0.5
    ) -> AIResult:
        pass
