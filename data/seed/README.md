# data/seed

The 9 sample Indian weather scenarios and the Judge Mode Patna Flood
timeline are defined in `backend/app/demo/scenarios.py` (structured Python
data, loaded automatically by `backend/app/seed.py` on first run) rather
than as static files here, so the seeding logic and the data it seeds stay
in one reviewable place.

This folder is where an externally supplied CSV/JSON dataset would be
dropped for the Datasets page's "Load Demo Dataset" flow to pick up in a
future iteration — the Dataset model and `/api/datasets` endpoint already
support cataloguing datasets from this location.
