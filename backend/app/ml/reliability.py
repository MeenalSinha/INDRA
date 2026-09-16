"""
Source reliability scoring. Never treats a source type as automatically
fake -- score is a blend of historical reliability, verification history,
source type prior, and metadata completeness. Source TYPE priors are a
starting point only, not a verdict.
"""

TYPE_PRIOR = {
    "government": 0.9,
    "weather_api": 0.85,
    "citizen_verified": 0.75,
    "news": 0.65,
    "citizen": 0.55,
    "social": 0.45,
    "dataset": 0.7,
}


def score_source(source_type: str, verification_history_count: int, metadata_completeness: float,
                  cross_source_agreement: float = 0.5):
    prior = TYPE_PRIOR.get(source_type, 0.5)
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
    return score, trust_level
