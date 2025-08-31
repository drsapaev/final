```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_db
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/utils", tags=["Utils"])

class TicketRequest(BaseModel):
    visit_id: int
    lang: str

class AuditLog(BaseModel):
    event: str
    entity: str
    entity_id: int
    payload: dict

@router.post("/print/ticket")
async def print_ticket(request: TicketRequest, db: Session = Depends(get_db)):
    from app.models import Visit
    visit = db.query(Visit).filter(Visit.id == request.visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    return {"message": f"Ticket for visit {visit.id} printed in {request.lang}"}

@router.post("/audit_logs")
async def log_action(log: AuditLog, db: Session = Depends(get_db)):
    # Здесь можно добавить запись в БД для аудита, если есть таблица
    return {"message": "Action logged"}
```