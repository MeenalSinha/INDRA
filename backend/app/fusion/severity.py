"""
Severity engine. Produces LOW/MODERATE/HIGH/CRITICAL plus a human-readable
list of reasons, so the UI can show real reasoning ("127 reports", "High
rainfall anomaly") instead of a bare label.
"""
from .. import config

HIGH_IMPACT_TYPES = {"Urban Flooding", "Cyclone", "Hailstorm"}
MODERATE_IMPACT_TYPES = {"Heavy Rainfall", "Thunderstorm", "Dust Storm", "Strong Winds"}


def compute_severity(event_type: str, report_count: int, spatial_spread_km: float,
                      has_weather_anomaly: bool, independent_source_count: int,
                      confidence: float, has_image_evidence: bool):
    score = 0
    reasons = []

    if report_count >= config.CRITICAL_REPORT_COUNT:
        score += 3
        reasons.append(f"{report_count} reports received")
    elif report_count >= config.HIGH_REPORT_COUNT:
        score += 2
        reasons.append(f"{report_count} reports received")
    elif report_count >= 3:
        score += 1
        reasons.append(f"{report_count} reports received")

    if event_type in HIGH_IMPACT_TYPES:
        score += 2
        reasons.append(f"High-impact category: {event_type}")
    elif event_type in MODERATE_IMPACT_TYPES:
        score += 1

    if has_weather_anomaly:
        score += 2
        reasons.append("Weather observation confirms anomaly vs local baseline")

    if spatial_spread_km and spatial_spread_km > 5:
        score += 1
        reasons.append(f"Spatial cluster spans approximately {spatial_spread_km:.1f} km")

    if independent_source_count >= 5:
        score += 1
        reasons.append(f"{independent_source_count} independent sources agree")

    if has_image_evidence:
        score += 1
        reasons.append("Supporting image evidence available")

    if confidence >= 0.85:
        score += 1
        reasons.append(f"High fusion confidence ({round(confidence * 100)}%)")

    if score >= 7:
        severity = "CRITICAL"
    elif score >= 5:
        severity = "HIGH"
    elif score >= 3:
        severity = "MODERATE"
    else:
        severity = "LOW"
        if not reasons:
            reasons.append("Limited corroborating evidence so far")

    return severity, reasons
