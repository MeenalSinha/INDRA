# INDRA — Event Fusion

The core differentiator. `backend/app/fusion/engine.py::fuse_cluster()`.

## The transformation

```
MULTIPLE REPORTS (already classified, deduplicated, geo-clustered)
        +
WEATHER OBSERVATIONS (nearby, recent)
        +
MEDIA EVIDENCE (image/video analysis)
        ↓
   SIX WEIGHTED FACTORS
        ↓
   ONE WEATHER EVENT
   (confidence + severity + evidence, created or updated)
```

## The six factors (weights in `fusion/engine.py::WEIGHTS`)

| Factor | Weight | Computed from |
|---|---|---|
| Semantic similarity | 0.20 | Mean pairwise TF-IDF cosine similarity across the cluster's report texts |
| Geo proximity | 0.20 | 1 − (spatial spread / 2× cluster radius) |
| Time proximity | 0.15 | 1 − (time spread / 3× duplicate time window) |
| Weather agreement | 0.20 | 0.9 if a nearby `WeatherObservation` is flagged anomalous, 0.55 if any exist, 0.35 if none |
| Source reliability | 0.10 | Mean of `ml/reliability.py::score_source()` across contributing sources |
| Independent evidence | 0.15 | Distinct source count + media count + report count, capped at 1.0 |

Each is a real number derived from real data in the cluster being fused —
not a placeholder. The confidence breakdown returned by `GET
/api/events/{id}` and shown on the Investigation screen is exactly this
dict, not a display-only reformatting of a single opaque score.

## Incremental clustering (added in this upgrade)

Both the clustering candidate query and the duplicate-detection candidate
query now pre-filter by a spatial bounding box around the incoming
report's coordinates before running DBSCAN / TF-IDF pairwise comparison,
instead of pulling every same-event-type report nationwide within the
rolling time window. Measured effect (`docs/UPGRADE_AUDIT.md`): per-
request latency growth over 2,000 sequential reports flattened from
22ms→65ms to a stable 20-34ms band, and total wall-clock time for the
same 2,000-report run dropped 40% (82.6s → 49.8s).

This does not change fusion semantics — DBSCAN still does the precise
haversine-based grouping on whatever the pre-filter lets through; the box
is padded generously (3x the cluster radius) so it is a performance
optimization, not a correctness change.

## Illustrative confidence values

Per the product principle established from the start: a Judge Mode
confidence like 94% is an output of the algorithm above running on
Judge-Mode-generated demo data, not a claimed real-world model accuracy.
This is stated in the README, in the product spec this system was built
from, and nowhere in the UI copy is it presented as a benchmark figure.

## Severity reasoning (`fusion/severity.py`)

Point-scored from report count, event-type impact class, weather
anomaly, spatial spread, independent source count, media evidence, and
confidence — returns both the LOW/MODERATE/HIGH/CRITICAL label and a
list of concrete reasons ("99 reports received", not "AI-powered
severity assessment").

## Known bug found and fixed during the previous audit

Judge Mode's live reports were originally merging into the pre-seeded,
already-VERIFIED historical Patna event via this exact clustering step,
because seeded backfill data and live data were treated identically. See
`docs/INDRA_AUDIT.md` §1 for the full writeup; the fix (`Report.is_seed_
data`, excluded from live clustering) is what makes a fresh Judge Mode
run produce its own new, genuinely-unverified event today.
