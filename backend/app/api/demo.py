from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..demo import simulator

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/start")
async def start_demo():
    return await simulator.start()


@router.post("/pause")
async def pause_demo():
    return await simulator.pause()


@router.post("/reset")
async def reset_demo(db: Session = Depends(get_db)):
    return await simulator.reset(db)


@router.get("/status")
def demo_status():
    return simulator.state.status()
