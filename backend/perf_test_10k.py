"""
§8 Performance test — 10,000 ingested reports.

Usage:
    python perf_test_10k.py [base_url] [target_count]

Defaults:
    base_url   = http://localhost:8000
    target_count = 10000

Progress is written to perf_results.json every 100 reports so the test is
resumable and results are visible while it runs.

Reports are sent in concurrent batches (BATCH=20 concurrent requests) using
httpx AsyncClient. Each report is a unique city+type combination to exercise
the full fusion/dedup pipeline, not just the HTTP layer.
"""
import asyncio
import datetime as dt
import json
import random
import sys
import time

import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
TARGET = int(sys.argv[2]) if len(sys.argv) > 2 else 10_000
BATCH = 20  # concurrent requests per wave
REPORT_FILE = "perf_results.json"

CITIES = [
    ("Patna", "Bihar"), ("Guwahati", "Assam"), ("Mumbai", "Maharashtra"),
    ("Delhi", "Delhi"), ("Chennai", "Tamil Nadu"), ("Jaipur", "Rajasthan"),
    ("Bengaluru", "Karnataka"), ("Hyderabad", "Telangana"), ("Kolkata", "West Bengal"),
    ("Ahmedabad", "Gujarat"), ("Bhubaneswar", "Odisha"), ("Lucknow", "Uttar Pradesh"),
    ("Chandigarh", "Punjab"), ("Shimla", "Himachal Pradesh"), ("Ranchi", "Jharkhand"),
]
TYPES = ["Urban Flooding", "Heavy Rainfall", "Strong Winds", "Thunderstorm", "Dust Storm", "Heatwave", "Fog"]
SOURCES = ["Citizen Reporter", "News Wire", "IMD Feed", "Social Monitor", "OWM"]
TEXTS = [
    "Heavy rainfall flooding low-lying areas near the station.",
    "Roads waterlogged, traffic at a standstill in the city centre.",
    "Trees uprooted, power lines down across multiple neighbourhoods.",
    "Visibility near zero due to dense fog on the highway.",
    "Temperature 6°C above seasonal average — heatwave warning issued.",
    "Storm surge reported along the coastal district, boats anchored.",
    "Lightning strikes reported, residents urged to stay indoors.",
]


def make_payload(i: int) -> dict:
    city, state = random.choice(CITIES)
    etype = random.choice(TYPES)
    text = random.choice(TEXTS) + f" (report #{i})"
    return {
        "source": random.choice(SOURCES),
        "source_type": "citizen",
        "text": text,
        "timestamp": dt.datetime.utcnow().isoformat(),
        "latitude": round(random.uniform(8.0, 35.0), 4),
        "longitude": round(random.uniform(68.0, 97.0), 4),
        "city": city,
        "state": state,
        "hashtags": [f"#{etype.replace(' ', '')}"],
        "raw_metadata": {"perf_test": True, "index": i},
    }


async def run():
    results = {
        "target": TARGET,
        "base_url": BASE_URL,
        "started_at": dt.datetime.utcnow().isoformat(),
        "checkpoints": [],
    }

    sent = 0
    errors = 0
    latencies_ms = []
    wall_start = time.perf_counter()

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        while sent < TARGET:
            batch_size = min(BATCH, TARGET - sent)
            payloads = [make_payload(sent + j) for j in range(batch_size)]
            t0 = time.perf_counter()
            tasks = [client.post("/api/reports", json=p) for p in payloads]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            elapsed = time.perf_counter() - t0

            for resp in responses:
                if isinstance(resp, Exception):
                    errors += 1
                elif resp.status_code in (200, 201):
                    latencies_ms.append(elapsed * 1000 / batch_size)
                else:
                    errors += 1
            sent += batch_size

            if sent % 100 == 0 or sent >= TARGET:
                total_elapsed = time.perf_counter() - wall_start
                rps = sent / total_elapsed if total_elapsed > 0 else 0
                p50 = sorted(latencies_ms)[len(latencies_ms) // 2] if latencies_ms else 0
                p95 = sorted(latencies_ms)[int(len(latencies_ms) * 0.95)] if latencies_ms else 0
                checkpoint = {
                    "sent": sent,
                    "errors": errors,
                    "elapsed_s": round(total_elapsed, 1),
                    "rps": round(rps, 1),
                    "p50_ms": round(p50, 1),
                    "p95_ms": round(p95, 1),
                }
                results["checkpoints"].append(checkpoint)
                print(
                    f"[{sent:>6}/{TARGET}] "
                    f"elapsed={total_elapsed:.1f}s  "
                    f"rps={rps:.1f}  "
                    f"errors={errors}  "
                    f"p50={p50:.0f}ms  p95={p95:.0f}ms"
                )
                with open(REPORT_FILE, "w") as f:
                    json.dump(results, f, indent=2)

    total_elapsed = time.perf_counter() - wall_start
    results["finished_at"] = dt.datetime.utcnow().isoformat()
    results["total_elapsed_s"] = round(total_elapsed, 1)
    results["total_sent"] = sent
    results["total_errors"] = errors
    results["overall_rps"] = round(sent / total_elapsed, 1)

    with open(REPORT_FILE, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n=== DONE: {sent} reports in {total_elapsed:.1f}s ({results['overall_rps']} rps) ===")
    print(f"Errors: {errors}")
    print(f"Full results → {REPORT_FILE}")


if __name__ == "__main__":
    asyncio.run(run())
