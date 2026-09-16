# INDRA ARCHITECTURE IMPLEMENTATION PLAN

## 1. Already Implemented
- **Frontend Framework:** React + Vite, Tailwind CSS, Leaflet Maps.
- **Backend Framework:** FastAPI, Uvicorn.
- **Current Database:** SQLite (Demo fallback) + PostgreSQL compatible (Live mode).
- **Current Event Fusion:** `fusion_engine.py` using TF-IDF/SentenceTransformer clustering + Geographic/Temporal bounds.
- **Current Real-Time/Streaming:** Kafka/Redpanda integration built in `pubsub.py` (Live) with in-process queues (Demo).
- **Current Ingestion Adapters:** REST API `/api/reports`, OWM Weather Poller (`weather_poller.py`).
- **Current WebSocket Implementation:** Real-time event notifications via `manager.py`.
- **Current Alert Implementation:** Email alerts (`notifications/email.py`) via SMTP.
- **Current Authentication:** JWT based role-access (Admin, Analyst) and simple Admin Token.
- **Current Judge Mode:** Built into `api/demo.py` and `demo/simulator.py` (Patna Flood scenario).
- **Current Docker Configuration:** Full `docker-compose.yml` with FastAPI, React, Redpanda, MinIO.
- **Current Object Storage:** MinIO/S3 configured in `storage.py`.
- **Current Tests:** Complete `pytest` suite running without errors (45 passing).

## 2. Partially Implemented
- **ML / AI Classifiers:** Basic HSV image thresholds and NLP semantic similarity exist, but lack deeper "Trust Assessment" or "Misinformation" scoring models.
- **Geo-Analytics:** Python `haversine` distance logic implemented. PostGIS models are bootstrapped but lack heavy spatial queries (H3 aggregation, risk zones).
- **Command Center UI:** Excellent foundational layout, but requires cleanup of visual presentation and language ("Remove AI-generated feel").
- **Admin Panel / Investigation:** Investigation page exists but needs deeper evidence graph exposure.

## 3. Missing
- **IMD / Government Connector:** Dedicated government API adapter with robust retry logic (only basic OpenWeatherMap exists).
- **Social Media Scraper / Adapter:** Real-time tweet/hashtag streaming connector.
- **Public Dataset Batch Upload:** CSV/Parquet batch ingestion adapter.
- **Video Analysis:** Frame extraction/metadata extraction for videos.
- **Historical Analytics Archive:** Long-term archival partitioning separate from live events.
- **SMS Provider Abstraction:** SMS integration for the alert engine.

## 4. Needs Replacement
- **Fake / Mock Data Generation:** Any remaining mock components in the demo simulator that attempt to fabricate API requests when live modes fail.
- **"AI-Powered" Language:** Dashboard buzzwords need replacement with concrete evidence metrics.

## 5. Needs Integration
- **PostGIS Real Spatial Logic:** Hooking up PostGIS geometries dynamically when `IS_POSTGRES` is true.
- **Evidence Graph UI:** Presenting the confidence breakdown factors visually to the user in the Investigation panel.
- **Risk Zones API:** Connecting geographic event density to a visual risk-layer on the map.
