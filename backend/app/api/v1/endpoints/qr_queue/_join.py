"""Split from qr_queue.py.
"""
from __future__ import annotations
from app.api.v1.endpoints.qr_queue._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.qr_queue._helpers import router

@router.post("/join/start", response_model=JoinSessionStartResponse)
def start_join_session(
    request: JoinSessionStartRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    """
    Начинает сессию присоединения к очереди (публичный эндпоинт)
    """

    service = QRQueueService(db)

    try:
        try:
            queue_service.validate_queue_token(db, request.token)
        except (QueueValidationError, QueueNotFoundError) as exc:
            raise ValueError(str(exc)) from exc

        logger.info(
            "[start_join_session] Запрос на начало сессии: token_present=%s, token_length=%d",
            bool(request.token),
            len(request.token or ""),
        )
        result = service.start_join_session(
            token=request.token,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("User-Agent"),
        )

        logger.info(
            "[start_join_session] Сессия успешно создана: session_token_present=%s, session_token_length=%d",
            bool(result.get("session_token")),
            len(result.get("session_token") or ""),
        )
        return JoinSessionStartResponse(**result)

    except ValueError as e:
        error_msg = str(e)
        logger.warning(
            "[start_join_session] ValueError: %s, token_present=%s, token_length=%d",
            error_msg,
            bool(request.token),
            len(request.token or ""),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    except Exception as e:
        error_msg = f"Ошибка начала сессии: {str(e)}"
        logger.error(
            "[start_join_session] Неожиданная ошибка: %s",
            error_msg,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg
        )


@router.post("/join/complete", response_model=dict[str, Any])
def complete_join_session(
    request: JoinSessionCompleteRequest, db: Session = Depends(get_db)
):
    """
    Завершает сессию присоединения к очереди (публичный эндпоинт)
    Поддерживает как одиночное, так и множественное присоединение
    """
    service = QRQueueService(db)

    try:
        logger.info(
            "[complete_join_session] Начало обработки запроса: session_token_present=%s, session_token_length=%d, patient_name_present=%s, phone_present=%s, specialist_count=%d",
            bool(request.session_token),
            len(request.session_token or ""),
            bool(request.patient_name),
            bool(request.phone),
            len(request.specialist_ids or []),
        )

        # Если передан список specialist_ids - множественное присоединение
        if request.specialist_ids and len(request.specialist_ids) > 0:
            result = service.complete_join_session_multiple(
                session_token=request.session_token,
                specialist_ids=request.specialist_ids,
                patient_name=request.patient_name,
                phone=request.phone,
                telegram_id=request.telegram_id,
            )
            logger.info(
                "[complete_join_session] Результат множественного присоединения: %s",
                result,
            )
            return JoinSessionCompleteMultipleResponse(**result)
        else:
            # Одиночное присоединение (старый способ)
            result = service.complete_join_session(
                session_token=request.session_token,
                patient_name=request.patient_name,
                phone=request.phone,
                telegram_id=request.telegram_id,
            )

            logger.info(
                "[complete_join_session] Результат получен: %s",
                result,
            )
            return JoinSessionCompleteResponse(**result)

    except ValueError as e:
        logger.warning(
            "[complete_join_session] ValueError: %s",
            str(e),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Internal server error")
    # Остальные исключения обрабатываются централизованными обработчиками
    # (exception_handlers.py)


