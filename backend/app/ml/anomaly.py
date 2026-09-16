"""
Anomaly detection for weather observations.

Uses Isolation Forest when enough historical observations exist to fit one
meaningfully; otherwise falls back to a transparent rule
(value > baseline * ratio) so the demo works from a cold start with only a
handful of seeded observations -- an honest fallback, not a fake model.
"""
import numpy as np
from sklearn.ensemble import IsolationForest

RULE_FALLBACK_RATIO = 2.5
MIN_SAMPLES_FOR_MODEL = 8


def predict(value: float, baseline: float, historical_values: list[float] | None = None) -> dict:
    if value is None or baseline is None:
        return {"is_anomaly": False, "score": 0.0}

    historical_values = historical_values or []
    if len(historical_values) >= MIN_SAMPLES_FOR_MODEL:
        X = np.array(historical_values + [value]).reshape(-1, 1)
        model = IsolationForest(contamination=0.15, random_state=42)
        model.fit(X)
        pred = model.predict(X)[-1]  # -1 = anomaly, 1 = normal
        raw_score = -model.score_samples(X)[-1]  # higher = more anomalous
        anomaly_score = round(min(1.0, max(0.0, (raw_score + 0.2) / 0.7)), 2)
        return {"is_anomaly": bool(pred == -1), "score": anomaly_score}

    # Rule-based fallback
    if baseline <= 0:
        return {"is_anomaly": value > 10, "score": 0.5}
    ratio = value / baseline
    is_anomaly = ratio >= RULE_FALLBACK_RATIO
    anomaly_score = round(min(1.0, max(0.0, (ratio - 1) / (RULE_FALLBACK_RATIO * 1.5))), 2)
    return {"is_anomaly": is_anomaly, "score": anomaly_score}
