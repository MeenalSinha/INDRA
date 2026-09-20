import os
from .registry import registry
from .interfaces import (
    TextClassifier,
    ImageAnalyzer,
    EmbeddingProvider,
    DuplicateDetector,
    AnomalyDetector,
    TrustAssessor
)
from .providers.text_classifier import RuleBasedTextClassifier
from .providers.image_analyzer import StubImageAnalyzer
from .providers.embeddings import TfIdfEmbeddingProvider, TransformersEmbeddingProvider
from .providers.duplicate_detector import DefaultDuplicateDetector
from .providers.anomaly_detector import DefaultAnomalyDetector
from .providers.trust_assessor import DefaultTrustAssessor

def init_ai_providers():
    """
    Registers the available AI providers and sets the active ones based on configuration.
    """
    # 1. Text Classification
    registry.register(TextClassifier, "rule_based", RuleBasedTextClassifier(), is_default=True)
    
    # 2. Image Analysis
    registry.register(ImageAnalyzer, "stub_image", StubImageAnalyzer(), is_default=True)
    
    # 3. Embeddings
    registry.register(EmbeddingProvider, "tfidf", TfIdfEmbeddingProvider())
    registry.register(EmbeddingProvider, "transformers", TransformersEmbeddingProvider())
    
    # Check env var for embedding provider
    backend = os.getenv("ML_BACKEND", "tfidf").lower()
    if backend == "transformers":
        try:
            registry.set_active(EmbeddingProvider, "transformers")
        except Exception:
            registry.set_active(EmbeddingProvider, "tfidf")
    else:
        registry.set_active(EmbeddingProvider, "tfidf")
        
    # 4. Duplicate Detection
    registry.register(DuplicateDetector, "default", DefaultDuplicateDetector(), is_default=True)
    
    # 5. Anomaly Detection
    registry.register(AnomalyDetector, "default", DefaultAnomalyDetector(), is_default=True)
    
    # 6. Trust Assessor
    registry.register(TrustAssessor, "default", DefaultTrustAssessor(), is_default=True)
