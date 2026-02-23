"""
API endpoints для обработки webhook от платежных провайдеров
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.provider_webhook_service import ProviderWebhookService

router = APIRouter()


@router.post("/click")
async def click_webhook(
    request: Request, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Webhook для Click платежной системы"""
    webhook_data = await request.json()
    return ProviderWebhookService(db).process_click_webhook(webhook_data)


@router.post("/payme")
async def payme_webhook(
    request: Request, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Webhook для Payme платежной системы (JSON-RPC)"""
    webhook_data = await request.json()
    auth_header = request.headers.get("Authorization")
    return ProviderWebhookService(db).process_payme_webhook(webhook_data, auth_header)


@router.post("/kaspi")
async def kaspi_webhook(
    request: Request, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Webhook для Kaspi Pay платежной системы"""
    webhook_data = await request.json()
    return ProviderWebhookService(db).process_kaspi_webhook(webhook_data)
