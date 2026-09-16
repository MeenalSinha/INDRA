"""
Duplicate / near-duplicate detection.

Rule: semantic_similarity > threshold AND distance < radius_km AND
time_gap < window_minutes => LIKELY_DUPLICATE. Originals are never deleted;
duplicates are flagged and linked (`duplicate_of_report_id`) so all raw
reports remain auditable, per requirement.
"""
from .. import config
from ..geo.utils import haversine_km
from .embeddings import pairwise_similarity


def find_duplicates(reports: list):
    """
    reports: list of Report ORM objects (already have .text, .latitude,
    .longitude, .timestamp, .id)
    Returns: list of dicts describing duplicate pairs found, e.g.
      {"report_id": 41, "duplicate_of": 32, "text_similarity": 0.91,
       "distance_km": 0.8, "time_gap_min": 4.5}
    """
    if len(reports) < 2:
        return []

    texts = [r.text or "" for r in reports]
    sim_matrix = pairwise_similarity(texts)

    results = []
    claimed = set()
    for i in range(len(reports)):
        if reports[i].id in claimed:
            continue
        for j in range(i + 1, len(reports)):
            if reports[j].id in claimed:
                continue
            text_sim = float(sim_matrix[i][j])
            distance_km = haversine_km(
                reports[i].latitude, reports[i].longitude,
                reports[j].latitude, reports[j].longitude,
            )
            time_gap_min = abs((reports[i].timestamp - reports[j].timestamp).total_seconds()) / 60.0

            if (
                text_sim > config.DUPLICATE_TEXT_SIMILARITY_THRESHOLD
                and distance_km < config.DUPLICATE_RADIUS_KM
                and time_gap_min < config.DUPLICATE_TIME_WINDOW_MIN
            ):
                results.append({
                    "report_id": reports[j].id,
                    "duplicate_of": reports[i].id,
                    "text_similarity": round(text_sim, 2),
                    "distance_km": round(distance_km, 2),
                    "time_gap_min": round(time_gap_min, 1),
                })
                claimed.add(reports[j].id)
    return results
