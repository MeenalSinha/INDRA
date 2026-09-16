"""
Sample Indian weather scenarios used to (a) seed the database with
realistic historical/verified events so the dashboard is populated on
first run, and (b) drive Judge Mode's live Patna Flood demonstration.
"""
import datetime as dt

# --- Historical / pre-seeded events (shown immediately on the dashboard) ---
SEED_EVENTS = [
    dict(city="Patna", state="Bihar", event_type="Urban Flooding", severity="CRITICAL",
         verification_status="VERIFIED", confidence=0.94, report_count=127, verified_report_count=103,
         lat=25.5941, lng=85.1376, hours_ago=2),
    dict(city="Guwahati", state="Assam", event_type="Heavy Rainfall", severity="HIGH",
         verification_status="UNDER_REVIEW", confidence=0.71, report_count=34, verified_report_count=0,
         lat=26.1445, lng=91.7362, hours_ago=3),
    dict(city="Mumbai", state="Maharashtra", event_type="Strong Winds", severity="MODERATE",
         verification_status="VERIFIED", confidence=0.81, report_count=19, verified_report_count=19,
         lat=19.0760, lng=72.8777, hours_ago=5),
    dict(city="New Delhi", state="Delhi", event_type="Fog", severity="LOW",
         verification_status="VERIFIED", confidence=0.77, report_count=11, verified_report_count=11,
         lat=28.6139, lng=77.2090, hours_ago=6),
    dict(city="Chennai", state="Tamil Nadu", event_type="Heavy Rainfall", severity="HIGH",
         verification_status="UNDER_REVIEW", confidence=0.68, report_count=28, verified_report_count=0,
         lat=13.0827, lng=80.2707, hours_ago=8),
    dict(city="Jodhpur", state="Rajasthan", event_type="Dust Storm", severity="MODERATE",
         verification_status="PROBABLE", confidence=0.63, report_count=15, verified_report_count=0,
         lat=26.2389, lng=73.0243, hours_ago=10),
    dict(city="Guwahati", state="Assam", event_type="Thunderstorm", severity="MODERATE",
         verification_status="VERIFIED", confidence=0.79, report_count=22, verified_report_count=22,
         lat=26.1445, lng=91.7362, hours_ago=14),
    dict(city="Jaipur", state="Rajasthan", event_type="Heatwave", severity="HIGH",
         verification_status="VERIFIED", confidence=0.85, report_count=41, verified_report_count=41,
         lat=26.9124, lng=75.7873, hours_ago=20),
    dict(city="Bhubaneswar", state="Odisha", event_type="Cyclone", severity="CRITICAL",
         verification_status="VERIFIED", confidence=0.91, report_count=88, verified_report_count=80,
         lat=20.2961, lng=85.8245, hours_ago=30),
]

# --- Judge Mode: Patna Flood live scenario ---------------------------------
# Each entry: (delay_seconds_after_start, payload)
def patna_flood_timeline():
    base = dt.datetime.utcnow()

    def ts(offset_min=0):
        return (base + dt.timedelta(minutes=offset_min)).isoformat()

    reports = []

    citizen_texts = [
        "Flood water entered our street near Kankarbagh.",
        "Water level rising fast near Gandhi Maidan, cannot walk through.",
        "Our lane in Rajendra Nagar is completely waterlogged.",
        "Ground floor of our building flooded, need help.",
        "Boyed Road submerged, vehicles stranded.",
    ]
    social_texts = [
        "Heavy rain near Gandhi Maidan, roads completely waterlogged #IMD #HeavyRain #Patna",
        "#IMD Patna flooding again this monsoon, Kankarbagh underwater",
        "Waterlogging reported in several parts of Patna city #Patna #Flood",
        "Traffic at a standstill on Bailey Road due to flooding #Patna",
    ]

    t = 0
    # T+0: first citizen report
    reports.append((t, dict(
        source="Citizen Reporter App", source_type="citizen",
        text=citizen_texts[0], city="Patna", state="Bihar",
        latitude=25.5941, longitude=85.1376, timestamp=ts(0), hashtags=[],
    )))
    t = 2
    for i, text in enumerate(social_texts[:2]):
        reports.append((t, dict(
            source="Social Media Monitor", source_type="social",
            text=text, city="Patna", state="Bihar",
            latitude=25.5941 + (i * 0.004), longitude=85.1376 + (i * 0.003),
            timestamp=ts(t), hashtags=["#IMD", "#Patna"],
        )))
        t += 1
    t = 4
    reports.append((t, dict(
        source="IMD Weather Feed", source_type="weather_api",
        text="Rainfall of 142 mm recorded in Patna in the last 6 hours, well above baseline.",
        city="Patna", state="Bihar", latitude=25.5968, longitude=85.1400, timestamp=ts(t), hashtags=[],
    )))
    t = 6
    reports.append((t, dict(
        source="Citizen Reporter App", source_type="citizen",
        text=citizen_texts[1], city="Patna", state="Bihar",
        latitude=25.5920, longitude=85.1350, timestamp=ts(t), hashtags=[],
        media_url="demo://patna-flood-1.jpg", media_type="image", media_category="Flooded Road",
    )))
    for i, text in enumerate(citizen_texts[2:] + social_texts[2:]):
        t += 1.5
        reports.append((t, dict(
            source="Citizen Reporter App" if i % 2 == 0 else "Social Media Monitor",
            source_type="citizen" if i % 2 == 0 else "social",
            text=text, city="Patna", state="Bihar",
            latitude=25.5941 + ((i % 5) * 0.003), longitude=85.1376 + ((i % 5) * 0.0025),
            timestamp=ts(t), hashtags=["#Patna"] if i % 2 else [],
        )))

    # Bulk wave of corroborating reports to reach the 127-report headline
    # number described in the product spec, arriving in a tight burst.
    t = 12
    for i in range(115):
        reports.append((t, dict(
            source=["Citizen Reporter App", "Social Media Monitor", "News Source"][i % 3],
            source_type=["citizen", "social", "news"][i % 3],
            text=citizen_texts[i % len(citizen_texts)],
            city="Patna", state="Bihar",
            latitude=25.5941 + ((i % 9) - 4) * 0.0015,
            longitude=85.1376 + ((i % 7) - 3) * 0.0015,
            timestamp=ts(t + i * 0.05), hashtags=["#IMD", "#Patna"] if i % 4 == 0 else [],
        )))

    return sorted(reports, key=lambda x: x[0])
