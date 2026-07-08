"""Split from qr_queue.py.
"""
from __future__ import annotations

from app.api.v1.endpoints.qr_queue._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.qr_queue._helpers import router


@router.post("/admin/qr-tokens/generate", response_model=QRTokenResponse)
def generate_qr_token(
    request: QRTokenGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Генерирует QR токен для присоединения к очереди
    Доступно администраторам, врачам и регистраторам
    """
    qr_service = QRQueueService(db)

    try:
        _ensure_doctor_can_mutate_specialist_queue(
            db,
            specialist_id=request.specialist_id,
            current_user=current_user,
        )
        target_date = None
        if request.target_date:
            target_date = datetime.strptime(request.target_date, "%Y-%m-%d").date()

        try:
            token_value, token_meta = queue_service.assign_queue_token(
                db,
            specialist_id=request.specialist_id,
            department=request.department,
            generated_by_user_id=current_user.id,
                target_date=target_date,
            expires_hours=request.expires_hours,
                is_clinic_wide=False,
            )
        except QueueValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        except QueueNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc

        base_url = qr_service._get_frontend_url()
        qr_url = f"{base_url}/queue/join?token={token_value}"
        qr_code_base64 = qr_service._generate_qr_code(qr_url)

        return QRTokenResponse(
            token=token_value,
            qr_url=qr_url,
            qr_code_base64=qr_code_base64,
            specialist_id=request.specialist_id,
            department=request.department,
            expires_at=(
                token_meta.get("expires_at").isoformat()
                if token_meta.get("expires_at")
                else None
            ),
            active=True,
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/admin/qr-tokens/generate-clinic", response_model=dict[str, Any])
def generate_clinic_qr_token(
    request: ClinicQRTokenGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Генерирует общий QR токен для всей клиники
    Пациент сможет выбрать несколько специалистов после сканирования
    Доступно только администраторам и регистраторам
    """
    try:
        target_date = date.today()
        if request.target_date:
            target_date = datetime.strptime(request.target_date, "%Y-%m-%d").date()

        token, token_data = queue_service.assign_queue_token(
            db,
            specialist_id=None,
            department="clinic",
            generated_by_user_id=current_user.id,
            target_date=target_date,
            expires_hours=request.expires_hours,
            is_clinic_wide=True,
        )

        # Генерируем QR код
        from app.services.qr_queue_service import QRQueueService

        service = QRQueueService(db)

        # Формируем URL для QR (используем метод из сервиса)
        base_url = service._get_frontend_url()
        qr_url = f"{base_url}/queue/join?token={token}"

        # Генерируем QR код
        qr_code_base64 = service._generate_qr_code(qr_url)

        return {
            "token": token,
            "qr_url": qr_url,
            "qr_code_base64": qr_code_base64,
            "is_clinic_wide": True,
            "day": target_date.isoformat(),
            "expires_at": (
                token_data.get("expires_at").isoformat()
                if token_data.get("expires_at")
                else None
            ),
            "active": True,
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/qr-tokens/{token}/info", response_model=QRTokenInfoResponse)
def get_qr_token_info(token: str, db: Session = Depends(get_db)):
    """
    Получает информацию о QR токене (публичный эндпоинт)
    """
    try:
        service = QRQueueService(db)

        token_info = service.get_qr_token_info(token)

        if not token_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR токен не найден или истек",
            )

        return QRTokenInfoResponse(**token_info)
    except HTTPException:
        raise
    except Exception as e:

        logger.error(
            "[get_qr_token_info] ОШИБКА: %s: %s",
            type(e).__name__,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/admin/qr-tokens/active", response_model=list[ActiveQRTokenResponse])
def get_active_qr_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
    limit: int = Query(default=100, ge=1, le=500, description="Количество записей"),
    offset: int = Query(default=0, ge=0, description="Смещение"),
):
    """
    Получает активные QR токены пользователя
    Доступно администраторам, врачам и регистраторам
    """
    service = QRQueueService(db)

    tokens = service.get_active_qr_tokens(current_user.id)

    # P1 FIX: cap results to prevent unbounded response
    return [ActiveQRTokenResponse(**token) for token in tokens[offset:offset + limit]]


@router.delete("/admin/qr-tokens/{token}", response_model=dict[str, Any])
def deactivate_qr_token(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Деактивирует QR токен
    Доступно администраторам, врачам и регистраторам
    """
    service = QRQueueService(db)

    success = service.deactivate_qr_token(token, current_user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR токен не найден или вы не являетесь его создателем",
        )

    return {"message": "QR токен успешно деактивирован"}


# ===================== УПРАВЛЕНИЕ СТАТУСАМИ ОЧЕРЕДИ =====================


class RestoreToNextRequest(BaseModel):
    """Запрос на восстановление пациента следующим в очереди"""
    reason: str | None = Field(None, description="Причина восстановления")


class SetIncompleteRequest(BaseModel):
    """Запрос на установку статуса incomplete"""
    reason: str = Field(..., min_length=3, max_length=200, description="Причина незавершённости")


