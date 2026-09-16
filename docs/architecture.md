# INDRA Architecture

## Pipeline

```mermaid
flowchart TD
    A[Data Sources<br/>Government / Weather APIs / Social / Citizen / Datasets / Media] --> B[Ingestion Layer<br/>adapters.py]
    B --> C[Processing<br/>normalize, validate, geocode]
    C --> D[AI / ML Engine<br/>classifier · duplicate · reliability · anomaly · image]
    D --> E[Geo-Analytics<br/>DBSCAN spatial clustering]
    E --> F[Event Fusion Engine<br/>fusion/engine.py]
    F --> G[Severity Engine]
    G --> H[(PostgreSQL / PostGIS<br/>SQLite in Demo Mode)]
    H --> I[FastAPI REST API]
    I --> J[WebSocket /ws/events]
    J --> K[Web Dashboard / Admin Panel]
    F --> L[Verification Workflow]
    L --> H
```

## Deployment topology (Docker Compose)

```mermaid
flowchart LR
    subgraph Browser
        UI[Frontend SPA]
    end
    UI -->|HTTP + WebSocket| NGINX[nginx :80]
    NGINX -->|/api, /ws proxy| API[FastAPI backend :8000]
    API --> PG[(Postgres + PostGIS)]
    API --> REDIS[(Redis)]
    API --> KAFKA[(Redpanda / Kafka)]
    API --> MINIO[(MinIO object storage)]
```

## Event Fusion (the core differentiator)

```mermaid
flowchart TD
    R1[127 raw reports] --> DUP[Duplicate detection<br/>TF-IDF + geo + time]
    DUP --> CLU[DBSCAN spatial clustering]
    CLU --> FUS[Fusion Engine]
    WX[Weather observations] --> FUS
    IMG[Image evidence] --> FUS
    FUS --> BREAKDOWN[Confidence breakdown:<br/>semantic · geo · time · weather ·<br/>source reliability · independent evidence]
    BREAKDOWN --> EVT[ONE Weather Event<br/>severity + confidence + evidence]
    EVT --> VER[Human verification]
```

## Demo Mode vs Live Mode

| Concern | Demo Mode (default) | Live Mode |
|---|---|---|
| Database | SQLite file, lat/lng floats | Postgres + PostGIS, `geography(Point)` |
| Streaming | In-process asyncio bus (`realtime/pubsub.py`) | Kafka / Redpanda topics |
| Cache / fan-out | Same in-process bus | Redis pub/sub |
| Object storage | Media referenced by URL/category only | MinIO (S3-compatible) |
| ML classification | Lexicon + scoring (explainable, no download) | Fine-tuned transformer, same `classify()` signature |
| Semantic similarity | TF-IDF + cosine (scikit-learn) | Sentence-Transformers embeddings, same `pairwise_similarity()` signature |
| Image analysis | Declared-category simulation with transparent confidence | OpenCV / lightweight CNN, same `analyze()` signature |

Switching from Demo to Live Mode is an environment-variable change
(`DATABASE_URL`, `REDIS_URL`, `KAFKA_BOOTSTRAP_SERVERS`, `MINIO_*` in
`.env`) plus swapping the four ML function bodies noted above — the API,
database schema, and frontend do not change.
