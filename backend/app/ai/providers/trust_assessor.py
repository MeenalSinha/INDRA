import time
from ..interfaces import TrustAssessor
from ..models import AIResult

class DefaultTrustAssessor(TrustAssessor):
    def __init__(self):
        self.type_prior = {
            "government": 0.9,
            "weather_api": 0.85,
            "citizen_verified": 0.75,
            "news": 0.65,
            "citizen": 0.55,
            "social": 0.45,
            "dataset": 0.7,
        }

    async def predict(
        self, 
        source_type: str, 
        verification_history_count: int, 
        metadata_completeness: float,
        cross_source_agreement: float = 0.5
    ) -> AIResult:
        start_time = time.time()
        
        prior = self.type_prior.get(source_type, 0.5)
        history_boost = min(0.15, verification_history_count * 0.01)
        score = (
            0.45 * prior
            + 0.20 * min(1.0, history_boost + 0.5)
            + 0.15 * metadata_completeness
            + 0.20 * cross_source_agreement
        )
        score = round(min(0.97, max(0.05, score)), 2)

        if score >= 0.75:
            trust_level = "HIGH TRUST"
        elif score >= 0.55:
            trust_level = "MEDIUM TRUST"
        elif score >= 0.35:
            trust_level = "LOW TRUST"
        else:
            trust_level = "UNKNOWN"
            
        return AIResult(
            prediction=trust_level,
            confidence=score,
            provider="DefaultTrustAssessor",
            model_version="1.0.0",
            processing_time_ms=(time.time() - start_time) * 1000,
            fallback_triggered=False,
            metadata={"source_type_prior": prior}
        )
