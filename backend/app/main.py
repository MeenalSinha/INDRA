import os
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from .core import config
from .core.database import Base, engine, ensure_schema
from .seed import run_seed
from .api import reports, events, analytics, alerts, demo, media, auth as auth_api
from .realtime.manager import websocket_endpoint
from .security.auth import check_rate_limit

app = FastAPI(
    title="INDRA — National Weather Intelligence Platform",
    description=(
        "Intelligent National Disaster & Weather Platform. Fuses multi-source "
        "weather reports into verified, actionable events. See /api/health "
        "for system status and README.md for architecture."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reports.router)
app.include_router(events.router)
app.include_router(analytics.router)
app.include_router(alerts.router)
app.include_router(demo.router)
app.include_router(media.router)
app.include_router(auth_api.router)

os.makedirs(os.getenv("LOCAL_MEDIA_DIR", "./data/media"), exist_ok=True)
app.mount("/media", StaticFiles(directory=os.getenv("LOCAL_MEDIA_DIR", "./data/media")), name="media")


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Exempt static assets / websocket upgrade / docs from the counter --
    # this guards the write/query-heavy API surface, not asset serving.
    if request.url.path.startswith("/api/"):
        try:
            check_rate_limit(request)
        except Exception as exc:
            status = getattr(exc, "status_code", 429)
            detail = getattr(exc, "detail", "Rate limit exceeded")
            return JSONResponse(status_code=status, content={"detail": detail})
    return await call_next(request)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    run_seed()


@app.on_event("startup")
async def on_startup_async():
    # §1: Start Kafka consumer relay (no-op if KAFKA_BOOTSTRAP_SERVERS unset)
    from .realtime.pubsub import start_kafka_consumer
    await start_kafka_consumer()

    # §5: Start OWM weather poller (no-op if OWM_API_KEY unset)
    from .ingestion.weather_poller import run_weather_poller
    from .core.database import SessionLocal
    import asyncio
    asyncio.create_task(run_weather_poller(SessionLocal))


def _api_status():
    return {
        "service": "INDRA API",
        "status": "online",
        "docs": "/docs",
        "websocket": "/ws/events",
        "mode": "LIVE (Postgres)" if config.IS_POSTGRES else "DEMO (SQLite, in-process streaming)",
    }


_frontend_dist = os.getenv("FRONTEND_DIST", "")
if not (_frontend_dist and os.path.isdir(_frontend_dist)):
    @app.get("/")
    def root():
        return _api_status()


@app.get("/api/status")
def api_status():
    return _api_status()


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    await websocket_endpoint(websocket)


# --- Optional combined single-process serving -----------------------------
# In Docker Compose, nginx serves frontend/ and proxies /api + /ws to this
# backend (separate services, matching the required architecture). For a
# quick single-command local run without Docker, this backend can also
# serve the built frontend directly if FRONTEND_DIST points at it -- so
# `uvicorn app.main:app` alone is enough to open http://localhost:8000/.
if _frontend_dist and os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")

