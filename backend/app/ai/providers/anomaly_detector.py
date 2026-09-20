import time
import numpy as np
from typing import Optional

from ..interfaces import AnomalyDetector
from ..models import AIResult

class DefaultAnomalyDetector(AnomalyDetector):
    def __init__(self, rule_fallback_ratio: float = 2.5, min_samples: int = 8):
        self.rule_fallback_ratio = rule_fallback_ratio
        self.min_samples = min_samples

    async def predict(self, value: float, baseline: float, historical_values: Optional[list[float]] = None) -> AIResult:
        start_time = time.time()
        
        if value is None or baseline is None:
            return AIResult(
                prediction=False,
                confidence=0.0,
                provider="DefaultAnomalyDetector",
                model_version="1.0.0",
                processing_time_ms=(time.time() - start_time) * 1000,
                fallback_triggered=True
            )

        historical_values = historical_values or []
        
        if len(historical_values) >= self.min_samples:
            from sklearn.ensemble import IsolationForest
            X = np.array(historical_values + [value]).reshape(-1, 1)
            model = IsolationForest(contamination=0.15, random_state=42)
            model.fit(X)
            pred = model.predict(X)[-1]  # -1 = anomaly, 1 = normal
            raw_score = -model.score_samples(X)[-1]  # higher = more anomalous
            anomaly_score = round(min(1.0, max(0.0, (raw_score + 0.2) / 0.7)), 2)
            
            return AIResult(
                prediction=bool(pred == -1),
                confidence=anomaly_score,
                provider="IsolationForest",
                model_version="1.0.0",
                processing_time_ms=(time.time() - start_time) * 1000,
                fallback_triggered=False
            )

        # Rule-based fallback
        if baseline <= 0:
            is_anomaly = value > 10
            anomaly_score = 0.5
        else:
            ratio = value / baseline
            is_anomaly = ratio >= self.rule_fallback_ratio
            anomaly_score = round(min(1.0, max(0.0, (ratio - 1) / (self.rule_fallback_ratio * 1.5))), 2)

        return AIResult(
            prediction=is_anomaly,
            confidence=anomaly_score,
            provider="RuleBasedFallback",
            model_version="1.0.0",
            processing_time_ms=(time.time() - start_time) * 1000,
            fallback_triggered=True,
            metadata={"ratio": ratio if baseline > 0 else None}
        )
