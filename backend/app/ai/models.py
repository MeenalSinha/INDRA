from typing import Any, Optional
from pydantic import BaseModel, Field

class AIResult(BaseModel):
    """
    Standard contract for all AI/ML predictions in INDRA.
    """
    prediction: Any = Field(..., description="The primary result of the model (e.g. event category, is_duplicate, anomaly_score).")
    confidence: float = Field(..., description="Confidence score from 0.0 to 1.0.")
    provider: str = Field(..., description="The name of the provider that generated this result (e.g. 'rule_based_classifier', 'sentence_transformers').")
    model_version: str = Field(..., description="Version of the model or ruleset used.")
    processing_time_ms: float = Field(0.0, description="Time taken to process the input.")
    fallback_triggered: bool = Field(False, description="Whether this result came from a fallback mechanism.")
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict, description="Additional provider-specific metadata or explainability info.")
