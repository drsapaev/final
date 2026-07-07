from __future__ import annotations

from app.api.v1.endpoints.admin_telegram._helpers import *  # noqa

@router.get("/telegram/settings")
def get_telegram_settings(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """Получить настройки Telegram"""
    try:
        telegram_settings = crud_clinic.get_settings_by_category(db, "telegram")

        result = {
            "bot_token": "",
            "webhook_url": "",
            "admin_chat_ids": [],
            "notifications_enabled": True,
            "appointment_reminders": True,
            "lab_results_notifications": True,
            "payment_notifications": True,
            "default_language": "ru",
            "supported_languages": ["ru", "uz-Latn"],
        }

        # Применяем сохраненные настройки
        for setting in telegram_settings:
            if setting.key in result:
                result[setting.key] = setting.value

        # Скрываем токен бота в ответе
        if result["bot_token"]:
            result["bot_token_masked"] = "***скрыт***"
            result["bot_token"] = "***скрыт***"

        return result
    except Exception as e:
        raise_admin_telegram_error(
            "settings-read",
            "Ошибка получения настроек Telegram",
            e,
        )


@router.put("/telegram/settings")
def update_telegram_settings(
    settings: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Обновить настройки Telegram"""
    try:
        # TG-AUDIT-28 P0-5: фильтруем masked bot_token placeholder.
        # GET /telegram/settings возвращает bot_token как "***скрыт***";
        # фронтенд отправляет его обратно при Save; без фильтра backend
        # записал бы masked значение в DB → бот ломается.
        if settings and isinstance(settings, dict):
            bt = settings.get("bot_token")
            if bt and isinstance(bt, str) and "***" in bt:
                settings = {k: v for k, v in settings.items() if k != "bot_token"}

        # Обновляем настройки в категории "telegram"
        updated_settings = crud_clinic.update_settings_batch(
            db, "telegram", settings, current_user.id
        )

        return {
            "success": True,
            "message": "Настройки Telegram обновлены",
            "updated_count": len(updated_settings),
        }
    except Exception as e:
        raise_admin_telegram_error(
            "settings-update",
            "Ошибка обновления настроек Telegram",
            e,
        )


@router.post("/telegram/test-bot")
def test_telegram_bot(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """Тестировать подключение к Telegram боту"""
    try:
        # Получаем токен бота
        bot_token = _get_configured_bot_token(db)
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Токен бота не настроен"
            )

        # Тестируем подключение к API Telegram
        response = httpx.get(
            f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10
        )

        if response.status_code == 200:
            bot_info = response.json()
            if bot_info.get("ok"):
                bot_data = bot_info["result"]

                # Сохраняем информацию о боте
                crud_clinic.update_settings_batch(
                    db,
                    "telegram",
                    {
                        "bot_username": bot_data.get("username"),
                        "bot_name": bot_data.get("first_name"),
                    },
                    current_user.id,
                )
                config_payload = {
                    "bot_token": bot_token,
                    "bot_username": bot_data.get("username"),
                    "bot_name": bot_data.get("first_name"),
                    "active": True,
                }
                if crud_telegram.get_telegram_config(db):
                    crud_telegram.update_telegram_config(db, config_payload)
                else:
                    crud_telegram.create_telegram_config(db, config_payload)

                return {
                    "success": True,
                    "message": "Подключение к боту успешно",
                    "bot_info": {
                        "id": bot_data.get("id"),
                        "username": bot_data.get("username"),
                        "first_name": bot_data.get("first_name"),
                        "can_join_groups": bot_data.get("can_join_groups"),
                        "can_read_all_group_messages": bot_data.get(
                            "can_read_all_group_messages"
                        ),
                    },
                }
            else:
                raise Exception(f"Ошибка API Telegram: {bot_info.get('description')}")
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

    except requests.RequestException as e:
        raise_admin_telegram_error(
            "test-bot-request",
            "Ошибка подключения к Telegram API",
            e,
            status.HTTP_400_BAD_REQUEST,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise_admin_telegram_error(
            "test-bot",
            "Ошибка тестирования бота",
            e,
        )


@router.post("/telegram/register-patient-commands")
async def register_patient_bot_commands(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Register patient bot commands in Telegram via the configured bot token."""
    try:
        bot_token = _get_configured_bot_token(db)
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bot token is not configured",
            )

        bot_service = await get_telegram_bot_service()
        bot_service.bot_token = bot_token
        ok, error = await bot_service.set_patient_bot_commands()
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": "Telegram patient bot commands were not registered",
                    "error": error,
                },
            )

        return {
            "success": True,
            "message": (
                "Telegram patient bot commands, menu button, and profile texts "
                "registered"
            ),
            "registered_languages": ["ru", "uz"],
            "menu_button": PATIENT_BOT_MENU_BUTTON,
            "profile_texts": PATIENT_BOT_PROFILE_TEXTS,
            "commands": {
                "ru": PATIENT_BOT_COMMANDS_RU,
                "uz": PATIENT_BOT_COMMANDS_UZ,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise_admin_telegram_error(
            "register-patient-commands",
            "Telegram patient bot command registration failed",
            e,
        )


@router.post("/telegram/register-staff-commands")
async def register_staff_bot_commands(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Register read-only staff bot commands with a dedicated staff bot token."""
    try:
        patient_bot_token = _get_configured_bot_token(db)
        token_status = _get_staff_bot_token_runtime_status(
            db, patient_bot_token=patient_bot_token
        )
        staff_bot_token = _get_configured_staff_bot_token(
            db, patient_bot_token=patient_bot_token
        )
        if not staff_bot_token or not token_status.get("ready"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Dedicated staff bot token is not configured",
                    "source": token_status.get("source"),
                    "source_key": token_status.get("source_key"),
                    "patient_bot_token_reused": bool(
                        token_status.get("patient_bot_token_reused")
                    ),
                },
            )

        commands = _staff_bot_read_only_command_payload()
        bot_service = await get_telegram_bot_service()
        ok, error = await bot_service.set_staff_bot_commands(
            staff_bot_token, commands=commands
        )
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": "Telegram staff bot commands were not registered",
                    "error": error,
                },
            )

        return {
            "success": True,
            "message": "Telegram staff bot read-only commands registered",
            "registered_commands": [item["command"] for item in commands],
            "state_changing_commands_registered": False,
            "token_returned_to_frontend": False,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise_admin_telegram_error(
            "register-staff-commands",
            "Telegram staff bot command registration failed",
            e,
        )


@router.post("/telegram/set-webhook")
def set_telegram_webhook(
    payload: TelegramWebhookRequest | None = Body(default=None),
    webhook_url: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Установить webhook для Telegram бота"""
    try:
        selected_webhook_url = (payload.webhook_url if payload else None) or webhook_url
        if not selected_webhook_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="webhook_url is required",
            )

        # Получаем токен бота
        bot_token = _get_configured_bot_token(db)
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Токен бота не настроен"
            )

        secret_token = secrets.token_urlsafe(32)

        # Устанавливаем webhook
        response = httpx.post(
            f"https://api.telegram.org/bot{bot_token}/setWebhook",
            json={"url": selected_webhook_url, "secret_token": secret_token},
            timeout=10,
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                # Сохраняем URL webhook
                crud_clinic.update_setting(
                    db, "webhook_url", {"value": selected_webhook_url}, current_user.id
                )
                config_payload = {
                    "bot_token": bot_token,
                    "bot_username": _get_configured_bot_username(db),
                    "webhook_url": selected_webhook_url,
                    "webhook_secret": secret_token,
                    "active": True,
                }
                if crud_telegram.get_telegram_config(db):
                    crud_telegram.update_telegram_config(db, config_payload)
                else:
                    crud_telegram.create_telegram_config(db, config_payload)

                return {
                    "success": True,
                    "message": "Webhook установлен успешно",
                    "webhook_url": selected_webhook_url,
                    "webhook_secret_configured": True,
                }
            else:
                raise Exception(
                    f"Ошибка установки webhook: {result.get('description')}"
                )
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

    except requests.RequestException as e:
        raise_admin_telegram_error(
            "set-webhook-request",
            "Ошибка установки webhook",
            e,
            status.HTTP_400_BAD_REQUEST,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise_admin_telegram_error(
            "set-webhook",
            "Ошибка установки webhook",
            e,
        )


@router.get("/telegram/webhook-info")
def get_telegram_webhook_info(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """Получить информацию о webhook"""
    try:
        # Получаем токен бота
        bot_token = _get_configured_bot_token(db)
        if not bot_token:
            return {"webhook_set": False, "message": "Токен бота не настроен"}

        # Получаем информацию о webhook
        response = httpx.get(
            f"https://api.telegram.org/bot{bot_token}/getWebhookInfo", timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                webhook_info = result["result"]
                return {
                    "webhook_set": bool(webhook_info.get("url")),
                    "webhook_info": _sanitize_telegram_webhook_info(webhook_info),
                }
            else:
                raise Exception(f"Ошибка API: {result.get('description')}")
        else:
            raise Exception(f"HTTP {response.status_code}")

    except requests.RequestException as e:
        return webhook_info_error_response(
            "webhook-info-request",
            "Ошибка подключения",
            e,
        )
    except Exception as e:
        return webhook_info_error_response(
            "webhook-info",
            "Ошибка получения информации о webhook",
            e,
        )


# ===================== ШАБЛОНЫ СООБЩЕНИЙ =====================


@router.get("/telegram/integration-status")
def get_telegram_integration_status(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """Return app-facing Telegram integration status without exposing secrets."""
    try:
        config = crud_telegram.get_telegram_config(db)
        bot_token = _get_configured_bot_token(db)
        bot_username = _get_configured_bot_username(db)
        staff_bot_token_status = _get_staff_bot_token_runtime_status(
            db, patient_bot_token=bot_token
        )
        telegram_users = crud_telegram.get_telegram_users(
            db, active_only=False, limit=100000
        )
        linked_users = [user for user in telegram_users if user.patient_id]

        webhook_info = None
        webhook_error = None
        if bot_token:
            try:
                webhook_info = _fetch_telegram_webhook_info(bot_token)
            except requests.RequestException as exc:
                webhook_error = "Telegram API unavailable"
                logger.warning(
                    "Admin Telegram integration status request failed error_type=%s",
                    type(exc).__name__,
                )
            except Exception as exc:
                webhook_error = "Telegram webhook status unavailable"
                logger.warning(
                    "Admin Telegram integration status failed error_type=%s",
                    type(exc).__name__,
                )

        webhook_set = bool(webhook_info and webhook_info.get("url"))
        webhook_url = (
            webhook_info.get("url")
            if webhook_info
            else getattr(config, "webhook_url", None)
        )

        return {
            "configured": bool(bot_token),
            "active": bool(getattr(config, "active", False) or bot_token),
            "bot_username": bot_username,
            "mode": "webhook" if webhook_set else "polling",
            "polling_ready": bool(bot_token and not webhook_set),
            "polling_command": "python -m app.scripts.telegram_polling_worker",
            "polling_task_name": "KosmedTelegramPollingWorker",
            "webhook_set": webhook_set,
            "webhook_url": webhook_url,
            "webhook_error": webhook_error,
            "pending_update_count": (
                webhook_info.get("pending_update_count") if webhook_info else None
            ),
            "qr_linking_enabled": bool(bot_username),
            "contact_linking_enabled": bool(bot_token),
            "linked_users": len(linked_users),
            "total_users": len(telegram_users),
            "supported_functions": [
                "ticket_qr_link",
                "contact_phone_link",
                "patient_queue",
                "patient_payments_debt",
                "patient_payments_mini_app_entry",
                "patient_status",
                "patient_language_notification_settings",
                "lab_results_pdf",
                "staff_link_start_token_handler",
                "telegram_ai_approval_notifications",
                "telegram_ai_approval_outcome_capture",
            ],
            "planned_functions": [
                "dedicated_staff_bot_token_readiness_contract",
                "staff_read_only_menu_contract",
                "staff_role_menu_enablement_status",
                "staff_role_linking_contract",
                "staff_role_linking_runtime",
                "staff_link_token_validation_contract",
                "staff_link_token_validation_runtime_helper",
                "staff_link_token_storage_migration_contract",
                "staff_server_side_authorization_contract",
                "staff_command_registration_contract",
                "staff_state_change_confirmation_contract",
                "staff_audit_logging_contract",
                "staff_role_menus",
                "staff_action_confirmations",
                "staff_audit_logging",
                "admin_notifications",
            ],
            "ai_approval": _build_telegram_ai_approval_status(),
            "patient_bot": {
                "version": "v1",
                "transport": "polling" if not webhook_set else "webhook",
                "supported_languages": [
                    {"code": "ru", "label": "Русский"},
                    {"code": "uz-Latn", "label": "O'zbekcha"},
                ],
                "default_language": "ru",
                "onboarding": "language_choice_then_contact_link",
                "commands": [
                    {
                        "command": f"/{command['command']}",
                        "label": command["description"],
                    }
                    for command in PATIENT_BOT_COMMANDS_RU
                ],
                "features": [
                    {
                        "key": "ticket_qr_link",
                        "label": "Привязка через QR чека",
                        "enabled": bool(bot_username),
                    },
                    {
                        "key": "contact_phone_link",
                        "label": "Привязка через номер телефона",
                        "enabled": bool(bot_token),
                    },
                    {
                        "key": "patient_booking_entrypoint",
                        "label": "Безопасная подсказка для записи",
                        "enabled": bool(bot_token),
                        "contract": PATIENT_BOOKING_ENTRY_CONTRACT,
                    },
                    {
                        "key": "patient_services_menu",
                        "label": "Видимая карта функций бота",
                        "enabled": bool(bot_token),
                    },
                    {
                        "key": "patient_queue",
                        "label": "Очередь пациента на сегодня",
                        "enabled": bool(bot_token),
                    },
                    {
                        "key": "patient_visits",
                        "label": "Мои визиты без медицинских деталей",
                        "enabled": bool(bot_token),
                    },
                    {
                        "key": "patient_payments_debt",
                        "label": "Оплаты и долг по визиту",
                        "enabled": bool(bot_token),
                    },
                    {
                        "key": "patient_payments_mini_app_entry",
                        "label": "Защищенный вход к оплатам пациента",
                        "enabled": bool(bot_token),
                        "contract": PATIENT_PAYMENT_ENTRY_CONTRACT,
                    },
                    {
                        "key": "patient_mini_app_manifest",
                        "label": "Mini App manifest пациента",
                        "enabled": bool(bot_token),
                        "contract": PATIENT_MINI_APP_MANIFEST_CONTRACT,
                    },
                    {
                        "key": "lab_results_pdf",
                        "label": "PDF-результаты лаборатории",
                        "enabled": bool(bot_token),
                    },
                    {
                        "key": "patient_forms_placeholder",
                        "label": "Анкеты пациента: безопасная заглушка Mini App",
                        "enabled": bool(bot_token),
                        "contract": PATIENT_FORMS_ENTRY_CONTRACT,
                    },
                    {
                        "key": "patient_documents_placeholder",
                        "label": "Документы и чеки: будущий защищенный кабинет",
                        "enabled": bool(bot_token),
                    },
                    {
                        "key": "doctor_schedule_placeholder",
                        "label": "Врачи и расписание: безопасная подсказка",
                        "enabled": bool(bot_token),
                    },
                    {
                        "key": "patient_cabinet_placeholder",
                        "label": "Кабинет пациента: будущий защищенный вход",
                        "enabled": bool(bot_token),
                    },
                    {
                        "key": "patient_language_notification_settings",
                        "label": "Настройки языка и уведомлений",
                        "enabled": bool(bot_token),
                    },
                    {
                        "key": "patient_support_contact",
                        "label": "Безопасная связь с клиникой",
                        "enabled": bool(bot_token),
                    },
                    {
                        "key": "staff_entry_placeholder",
                        "label": "Режим сотрудника: вход по персональной ссылке",
                        "enabled": bool(bot_token),
                    },
                ],
                "results_delivery": "telegram_pdf",
                "max_pdf_reports_per_request": 3,
            },
            "staff_bot": _build_staff_bot_status(webhook_set, staff_bot_token_status),
            "transition_path": (
                "Set webhook when a public HTTPS backend URL is available; "
                "stop polling before webhook is enabled."
            ),
        }
    except Exception as e:
        raise_admin_telegram_error(
            "integration-status",
            "Ошибка получения статуса Telegram интеграции",
            e,
        )


# ============================================================
# === TEMPLATES & MESSAGING ENDPOINTS ===
# ============================================================
