"""
Confidence computation for the Event Fusion Engine.

Pure functions — no DB access, no ORM imports. All inputs are plain Python
values so this module can be unit-tested without a database session.

compute_breakdown()  ->  dict of factor scores (0..1 each)
compute_confidence() ->  weighted scalar (0..0.97)
"""
from collections import Counter
from ..core import config
from ..geo.utils import haversine_km
from ..ml.embeddings import pairwise_similarity
from ..ml.reliability import predict as score_source

WEIGHTS = {
    "semantic_similarity": 0.20,
    "geo_proximity": 0.20,
    "time_proximity": 0.15,
    "weather_agreement": 0.20,
    "source_reliability": 0.10,
    "independent_evidence": 0.15,
}


def _spatial_spread_km(coords: list[tuple[float, float]]) -> float:
    """Maximum pairwise haversine distance between (lat, lng) points."""
    if len(coords) < 2:
        return 0.0
    max_d = 0.0
    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            max_d = max(max_d, haversine_km(*coords[i], *coords[j]))
    return max_d


def compute_breakdown(
    texts: list[str],
    coords: list[tuple[float, float]],
    timestamps: list,
    weather_obs: list,
    source_types: list[str],
    source_names: list[str],
    media_counts: list[int],
    report_count: int,
) -> dict:
    """
    Compute per-factor confidence scores.

    Args:
        texts:        Report text strings.
        coords:       (lat, lng) tuples for reports with valid coordinates.
        timestamps:   datetime objects for all reports.
        weather_obs:  WeatherObservation ORM objects (duck-typed: .is_anomaly).
        source_types: source_type string per report.
        source_names: source_name string per report (for distinct-source count).
        media_counts: number of media items per report.
        report_count: total number of reports in the cluster.

    Returns:
        dict with keys matching WEIGHTS; all values are floats in [0, 1].
    """
    # --- semantic similarity ---------------------------------------------------
    if len(texts) >= 2:
        sim_matrix = pairwise_similarity(texts)
        vals = [sim_matrix[i][j] for i in range(len(texts)) for j in range(i + 1, len(texts))]
        semantic_similarity = sum(vals) / len(vals) if vals else 0.5
    else:
        semantic_similarity = 0.6  # single report: neutral-ish

    # --- geo proximity ---------------------------------------------------------
    spread_km = _spatial_spread_km(coords)
    geo_proximity = max(0.1, min(1.0, 1 - (spread_km / (config.CLUSTER_EPS_KM * 2))))

    # --- time proximity --------------------------------------------------------
    if len(timestamps) > 1:
        time_spread_min = (max(timestamps) - min(timestamps)).total_seconds() / 60.0
    else:
        time_spread_min = 0
    time_proximity = max(0.1, min(1.0, 1 - (time_spread_min / (config.DUPLICATE_TIME_WINDOW_MIN * 3))))

    # --- weather agreement -----------------------------------------------------
    anomaly_hits = [w for w in weather_obs if w.is_anomaly]
    weather_agreement = 0.9 if anomaly_hits else (0.55 if weather_obs else 0.35)

    # --- source reliability ----------------------------------------------------
    reliability_scores = []
    for src_type, lat_text_available in zip(source_types, [True] * len(source_types)):
        result = score_source(
            src_type or "citizen",
            verification_history_count=0,
            metadata_completeness=0.8 if lat_text_available else 0.4,
        )
        reliability_scores.append(result["score"])
    source_reliability = sum(reliability_scores) / len(reliability_scores) if reliability_scores else 0.5

    # --- independent evidence --------------------------------------------------
    distinct_sources = len({n for n in source_names if n})
    total_media = sum(media_counts)
    independent_evidence = min(1.0, 0.10 * distinct_sources + 0.05 * total_media + 0.05 * report_count)
    independent_evidence = max(0.2, independent_evidence)

    return {
        "semantic_similarity": round(semantic_similarity, 2),
        "geo_proximity": round(geo_proximity, 2),
        "time_proximity": round(time_proximity, 2),
        "weather_agreement": round(weather_agreement, 2),
        "source_reliability": round(source_reliability, 2),
        "independent_evidence": round(independent_evidence, 2),
        # Expose derived values callers need so they don't re-compute
        "_spread_km": spread_km,
        "_anomaly_hits": len(anomaly_hits),
        "_distinct_sources": distinct_sources,
        "_total_media": total_media,
    }


def compute_confidence(breakdown: dict) -> float:
    """Weighted blend of factor scores, capped at 0.97."""
    raw = sum(breakdown[k] * WEIGHTS[k] for k in WEIGHTS)
    return min(0.97, round(raw, 2))
