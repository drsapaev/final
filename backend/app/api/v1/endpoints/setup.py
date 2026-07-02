from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.setup import SetupInitializeIn, SetupInitializeOut, SetupStatusOut
from app.services.setup_service import SetupService

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatusOut, summary="Minimal setup state")
def get_setup_status(db: Session = Depends(get_db)):
    return SetupService(db).get_status()


@router.post(
    "/initialize",
    response_model=SetupInitializeOut,
    summary="Initialize clinic deployment from first-run setup",
)
def initialize_setup(body: SetupInitializeIn, db: Session = Depends(get_db)):
    return SetupService(db).initialize(body)
