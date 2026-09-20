"""
Judge Mode / Demo Mode simulator.

Feeds the Patna Flood scenario (demo/scenarios.py) through the exact same
`ingest_report()` pipeline used by the real REST ingestion API -- per the
spec's "do not simply animate fake numbers in the frontend" requirement.
Runs as an asyncio background task so START/PAUSE/RESET can control it
without blocking the API.
"""
import asyncio
import datetime as dt
from .. import models
from ..core.database import SessionLocal
from ..ingestion.adapters import ingest_report
from ..realtime import pubsub
from .scenarios import patna_flood_timeline

STAGE_LABELS = [
    (0, "Citizen report arrives"),
    (2, "Social media reports arrive"),
    (4, "Weather observation arrives"),
    (6, "Image evidence arrives"),
    (8, "AI detects event category"),
    (10, "Duplicate reports are grouped"),
    (12, "Geospatial clustering identifies event"),
    (14, "Confidence increases"),
    (16, "Event becomes CRITICAL"),
    (18, "Admin verification screen appears"),
    (20, "Dashboard updates"),
]

# Compress the scenario's minute-offsets into real seconds so a judge sees
# the full story in well under a minute.
TIME_SCALE_SECONDS_PER_MINUTE = 1.4


class JudgeModeState:
    def __init__(self):
        self.running = False
        self.paused = False
        self.task: asyncio.Task | None = None
        self.processed = 0
        self.total = 0

    def status(self):
        return {
            "running": self.running, "paused": self.paused,
            "processed": self.processed, "total": self.total,
        }


state = JudgeModeState()


async def _run():
    timeline = patna_flood_timeline()
    state.total = len(timeline)
    state.processed = 0
    last_offset = 0

    await pubsub.publish("demo.stage", {"label": "Judge Mode started — Patna Flood scenario", "offset": 0})

    db = SessionLocal()
    try:
        for offset, payload in timeline:
            while state.paused:
                await asyncio.sleep(0.2)
                if not state.running:
                    return
            if not state.running:
                return

            wait = max(0.0, (offset - last_offset) * TIME_SCALE_SECONDS_PER_MINUTE)
            await asyncio.sleep(min(wait, 2.5))  # cap so 115-report burst stays fast
            last_offset = offset

            for stage_offset, label in STAGE_LABELS:
                if abs(stage_offset - offset) < 0.6:
                    await pubsub.publish("demo.stage", {"label": label, "offset": offset})

            await ingest_report(db, payload)
            state.processed += 1

        await pubsub.publish("demo.stage", {"label": "Patna Flood scenario complete", "offset": 20})
    finally:
        db.close()
        state.running = False


async def start():
    if state.running:
        return state.status()
    state.running = True
    state.paused = False
    state.task = asyncio.create_task(_run())
    return state.status()


async def pause():
    state.paused = not state.paused
    return state.status()


async def reset(db):
    """
    Full clean-slate reset: judge mode mutates shared state (it fuses into
    the real seeded Patna event, updates confidence/report counts, may
    create alerts, etc.), so partial "undo" is unreliable. RESET instead
    wipes every table and reseeds from scratch -- the same guarantee a
    judge needs between back-to-back demo runs.
    """
    state.running = False
    state.paused = False
    if state.task:
        state.task.cancel()
    state.processed = 0
    state.total = 0

    from ..core.database import Base
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    db.close()

    from .. import seed as seed_module
    await seed_module.run_seed()

    await pubsub.publish("demo.reset", {})
    return state.status()

