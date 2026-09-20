import re
import time
from typing import Optional

from ..interfaces import TextClassifier
from ..models import AIResult

CATEGORIES = {
    "Urban Flooding": {
        "terms": {
            "flood": 1.0, "flooded": 1.0, "flooding": 1.0, "waterlogged": 0.9,
            "waterlogging": 0.9, "submerged": 0.8, "water entered": 0.9,
            "drainage": 0.4, "overflowing": 0.6, "inundated": 0.8,
        },
    },
    "Heavy Rainfall": {
        "terms": {
            "heavy rain": 1.0, "heavy rainfall": 1.0, "downpour": 0.8,
            "torrential": 0.9, "continuous rain": 0.6, "rain": 0.3,
            "showers": 0.3, "mm rainfall": 0.7,
        },
    },
    "Thunderstorm": {
        "terms": {
            "thunderstorm": 1.0, "thunder": 0.8, "lightning strike": 0.7,
            "storm": 0.5, "squall": 0.6,
        },
    },
    "Lightning": {
        "terms": {"lightning": 0.9, "struck by lightning": 1.0, "bolt": 0.3},
    },
    "Heatwave": {
        "terms": {
            "heatwave": 1.0, "heat wave": 1.0, "extreme heat": 0.9,
            "scorching": 0.7, "high temperature": 0.5, "sunstroke": 0.6,
        },
    },
    "Fog": {
        "terms": {
            "fog": 1.0, "foggy": 0.9, "low visibility": 0.8, "mist": 0.5,
            "smog": 0.5,
        },
    },
    "Dust Storm": {
        "terms": {
            "dust storm": 1.0, "dust": 0.5, "sandstorm": 0.9, "haze": 0.3,
        },
    },
    "Strong Winds": {
        "terms": {
            "strong wind": 1.0, "high wind": 0.9, "gusty wind": 0.8,
            "gale": 0.7, "windy": 0.4, "uprooted": 0.6, "trees fell": 0.6,
        },
    },
    "Hailstorm": {
        "terms": {"hail": 1.0, "hailstorm": 1.0, "hailstones": 0.9},
    },
    "Cyclone": {
        "terms": {
            "cyclone": 1.0, "cyclonic": 0.9, "landfall": 0.6,
            "storm surge": 0.7, "coastal warning": 0.5,
        },
    },
}

def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\s#]", " ", (text or "").lower())


class RuleBasedTextClassifier(TextClassifier):
    """
    Transparent lexicon + scoring classifier. Each event category has a set of
    weighted trigger terms. Explainable and fast.
    """
    
    async def predict(self, text: str, hashtags: Optional[list[str]] = None) -> AIResult:
        start_time = time.time()
        
        norm = _normalize(text)
        tag_text = " ".join(h.lower().lstrip("#") for h in (hashtags or []))
        haystack = f"{norm} {tag_text}"

        scores = {}
        for category, cfg in CATEGORIES.items():
            matched_weight = 0.0
            matches = 0
            for term, weight in cfg["terms"].items():
                if term in haystack:
                    matched_weight += weight
                    matches += 1
            if matches:
                confidence = min(0.97, 0.45 + matched_weight * 0.22 + 0.05 * (matches - 1))
                scores[category] = round(confidence, 2)

        if not scores:
            best_category = "Other"
            confidence = 0.30
        else:
            best_category = max(scores, key=scores.get)
            confidence = scores[best_category]
            
        processing_time = (time.time() - start_time) * 1000

        return AIResult(
            prediction=best_category,
            confidence=confidence,
            provider="RuleBasedTextClassifier",
            model_version="1.0.0",
            processing_time_ms=processing_time,
            fallback_triggered=False,
            metadata={"all_scores": scores}
        )
