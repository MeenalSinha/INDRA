import time
from typing import Any

from ..interfaces import DuplicateDetector
from ..registry import get_embedding_provider
from ...core import config
from ...geo.utils import haversine_km

class DefaultDuplicateDetector(DuplicateDetector):
    async def find_duplicates(self, reports: list[Any]) -> list[dict[str, Any]]:
        """
        reports: list of Report ORM objects (already have .text, .latitude,
        .longitude, .timestamp, .id)
        """
        if len(reports) < 2:
            return []

        embedding_provider = get_embedding_provider()
        texts = [r.text or "" for r in reports]
        
        # We await the pairwise similarity
        sim_matrix = await embedding_provider.pairwise_similarity(texts)

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
