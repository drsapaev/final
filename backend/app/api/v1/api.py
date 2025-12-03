# app/api/v1/api.py
from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

# CRUD departments endpoint registered

# подключаем router из каждого модуля
from app.api.v1.endpoints import admin_departments  # CRUD для управления отделениями
from app.api.v1.endpoints import backup_management  # Database backup management
from app.api.v1.endpoints import ai  # Новый AI модуль
from app.api.v1.endpoints import ai_analytics  # Расширенная аналитика AI
from app.api.v1.endpoints import billing  # Автоматическое выставление счетов
from app.api.v1.endpoints import cloud_printing  # Облачная печать
from app.api.v1.endpoints import departments  # Управление отделениями/вкладками
from app.api.v1.endpoints import discount_benefits  # Система скидок и льгот
from app.api.v1.endpoints import doctor_info  # Информация о врачах и отделениях
from app.api.v1.endpoints import dynamic_pricing  # Динамическое ценообразование
from app.api.v1.endpoints import feature_flags  # Фича-флаги
from app.api.v1.endpoints import group_permissions  # Разрешения групп пользователей
from app.api.v1.endpoints import medical_equipment  # Медицинское оборудование
from app.api.v1.endpoints import payment_settings  # Настройки платежных провайдеров
from app.api.v1.endpoints import payment_reconciliation  # Payment reconciliation
from app.api.v1.endpoints import qr_queue  # QR очереди
from app.api.v1.endpoints import (
    queue_cabinet_management,  # Управление кабинетами в очередях
)
from app.api.v1.endpoints import queue_limits  # Лимиты очередей
from app.api.v1.endpoints import registrar_notifications  # Уведомления регистратуры
from app.api.v1.endpoints import registrar_wizard  # Новый мастер регистрации
from app.api.v1.endpoints import reports  # Система отчетов
from app.api.v1.endpoints import system_management  # Система бэкапов и мониторинга
from app.api.v1.endpoints import telegram_bot  # Telegram Bot
from app.api.v1.endpoints import user_data_transfer  # Передача данных пользователей
from app.api.v1.endpoints import wait_time_analytics  # Аналитика времени ожидания
from app.api.v1.endpoints import (  # online_queue,  # Временно отключено; online_queue_new,  # Временно отключено; queue,  # Временно отключено
    activation as activation_ep,
    admin_ai,
    admin_clinic,
    admin_display,
    admin_doctors,
    admin_providers,
    admin_stats,
    admin_telegram,
    admin_users,
    advanced_analytics,
    ai_integration,
    analytics,
    analytics_export,
    analytics_kpi,
    analytics_predictive,
    analytics_visualization,
    api_documentation,
    appointment_flow,
    appointments,
    auth,
    authentication,
    board as board_ep,
    cardio,
    clinic_management,
    dental,
    derma,
    display_websocket,
    docs,
    doctor_integration,
    email_sms_enhanced,
    emr_ai,
    emr_ai_enhanced,
    emr_export,
    emr_lab_integration,
    emr_templates,
    emr_versioning_enhanced,
    fcm_notifications,
    file_system,
    file_test,
    file_upload_json,
    file_upload_simple,
    health as health_ep,
    lab_specialized,
    mobile_api,
    mobile_api_extended,
    notifications,
    password_reset,
    patients,
    payment_webhook,
    payments,
    phone_verification,
    print as print_ep,
    print_api,
    print_templates,
    queue_reorder,
    queues,
    registrar_integration,
    reports as reports_ep,
    schedule,
    services,
    sms_providers,
    specialized_panels,
    telegram_bot_management,
    telegram_integration,
    telegram_notifications,
    telegram_webhook,
    telegram_webhook_enhanced,
    two_factor_auth,
    two_factor_devices,
    two_factor_sms_email,
    user_management,
    visits,
    webhooks,
    websocket_auth,
)

# Импортируем эндпоинты управления миграциями
from app.api.v1.endpoints.migration_management import (
    router as migration_management_router,
)

# Импортируем эндпоинты утренней сборки
from app.api.v1.endpoints.morning_assignment import router as morning_assignment_router
from app.api.v1.endpoints.payment_webhooks import router as payment_webhooks_router

# Импортируем новые payment endpoints
from app.api.v1.endpoints.payments import router as payments_new_router

# Импортируем новый queue endpoint
from app.api.v1.endpoints.queue import router as queue_router

# Импортируем эндпоинты управления безопасностью
from app.api.v1.endpoints.security_management import (
    router as security_management_router,
)

# Импортируем эндпоинты подтверждения визитов
from app.api.v1.endpoints.visit_confirmation import router as visit_confirmation_router

api_router = APIRouter()

# Auth (/login, /me и т.д.)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Простая авторизация (временное решение)
from app.api.v1.endpoints import simple_auth

api_router.include_router(simple_auth.router, prefix="/auth", tags=["simple-auth"])

# Минимальная авторизация (без зависимостей от моделей)
from app.api.v1.endpoints import minimal_auth

api_router.include_router(minimal_auth.router, prefix="/auth", tags=["minimal-auth"])
api_router.include_router(patients.router, prefix="/patients", tags=["patients"])
api_router.include_router(visits.router, prefix="/visits", tags=["visits"])
api_router.include_router(services.router, prefix="/services")
api_router.include_router(
    departments.router, prefix="/departments", tags=["departments"]
)
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(
    payments_new_router, prefix="/payments", tags=["payments-new"]
)
api_router.include_router(
    payment_webhooks_router, prefix="/payments/webhook", tags=["payment-webhooks"]
)

# Эндпоинты подтверждения визитов (публичные, без авторизации)
api_router.include_router(visit_confirmation_router, tags=["visit-confirmation"])

# Эндпоинты утренней сборки (админ/регистратор)
api_router.include_router(morning_assignment_router, tags=["morning-assignment"])

# Эндпоинты управления безопасностью (только админ)
api_router.include_router(security_management_router, tags=["security-management"])

# Эндпоинты управления миграциями (только админ)
api_router.include_router(migration_management_router, tags=["migration-management"])
# Эндпоинты управления фича-флагами
api_router.include_router(feature_flags.router, tags=["feature-flags"])
# Эндпоинты QR очередей (основной роутер для queue)
api_router.include_router(qr_queue.router, prefix="/queue", tags=["qr-queue"])
# Эндпоинты лимитов очередей
api_router.include_router(queue_limits.router, prefix="/admin", tags=["queue-limits"])
# Эндпоинты управления кабинетами в очередях
api_router.include_router(
    queue_cabinet_management.router, prefix="/admin", tags=["queue-cabinet-management"]
)
# Эндпоинты передачи данных пользователей
api_router.include_router(
    user_data_transfer.router, prefix="/admin/user-data", tags=["user-data-transfer"]
)
# Эндпоинты разрешений групп пользователей
api_router.include_router(
    group_permissions.router, prefix="/admin/permissions", tags=["group-permissions"]
)
# Эндпоинты уведомлений регистратуры
api_router.include_router(
    registrar_notifications.router,
    prefix="/registrar/notifications",
    tags=["registrar-notifications"],
)
# Эндпоинты информации о врачах и отделениях
api_router.include_router(
    doctor_info.router, prefix="/doctor-info", tags=["doctor-info"]
)
# Эндпоинты аналитики времени ожидания
api_router.include_router(
    wait_time_analytics.router,
    prefix="/analytics/wait-time",
    tags=["wait-time-analytics"],
)
# Эндпоинты расширенной аналитики AI
api_router.include_router(
    ai_analytics.router, prefix="/analytics/ai", tags=["ai-analytics"]
)
# Эндпоинты системы отчетов
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
# Эндпоинты системы бэкапов и мониторинга
api_router.include_router(
    system_management.router, prefix="/system", tags=["system-management"]
)
# Эндпоинты системы webhook'ов
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(queues.router, prefix="/queues", tags=["queues"])
api_router.include_router(appointments.router, tags=["appointments"])
# api_router.include_router(online_queue.router, tags=["online-queue"])  # Временно отключено
# api_router.include_router(online_queue_new.router, tags=["online-queue-new"])  # Временно отключено
api_router.include_router(registrar_integration.router, tags=["registrar"])
api_router.include_router(registrar_wizard.router, tags=["registrar-wizard"])
api_router.include_router(doctor_integration.router, tags=["doctor-integration"])
api_router.include_router(
    print_templates.router, prefix="/print/templates", tags=["print-templates"]
)
api_router.include_router(print_api.router, prefix="/print", tags=["print-api"])
api_router.include_router(ai_integration.router, prefix="/ai", tags=["ai-integration"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])  # Новые AI endpoints

# MCP (Model Context Protocol) endpoints
try:
    from app.api.v1.endpoints import mcp

    api_router.include_router(mcp.router, prefix="/mcp", tags=["mcp"])
except ImportError:
    logger.info("MCP module not available - skipping MCP routes")
api_router.include_router(
    telegram_bot.router, prefix="/telegram/bot", tags=["telegram-bot"]
)  # Telegram Bot
api_router.include_router(
    telegram_integration.router, prefix="/telegram", tags=["telegram-integration"]
)
api_router.include_router(
    display_websocket.router, prefix="/display", tags=["display-websocket"]
)
api_router.include_router(print_ep.router, tags=["print"])
api_router.include_router(board_ep.router, tags=["board"])
api_router.include_router(reports_ep.router, tags=["reports"])
api_router.include_router(payment_webhook.router, tags=["webhooks"])
api_router.include_router(payment_reconciliation.router, prefix="/payments", tags=["payment-reconciliation"])
api_router.include_router(admin_ai.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_clinic.router, prefix="/admin", tags=["admin"])
api_router.include_router(
    clinic_management.router, prefix="/clinic", tags=["clinic-management"]
)
api_router.include_router(payment_settings.router, tags=["payment-settings"])
api_router.include_router(
    admin_departments.router, prefix="/admin/departments", tags=["admin-departments"]
)
api_router.include_router(admin_display.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_doctors.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_providers.router, tags=["admin"])
api_router.include_router(admin_telegram.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_stats.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_users.router)
api_router.include_router(mobile_api.router, prefix="/mobile", tags=["mobile"])
api_router.include_router(
    mobile_api_extended.router, prefix="/mobile", tags=["mobile-extended"]
)
api_router.include_router(emr_templates.router, prefix="/emr", tags=["emr-templates"])
api_router.include_router(emr_ai.router, prefix="/emr/ai", tags=["emr-ai"])
api_router.include_router(
    emr_ai_enhanced.router, prefix="/emr/ai-enhanced", tags=["emr-ai-enhanced"]
)
api_router.include_router(
    emr_versioning_enhanced.router, prefix="/emr/versions", tags=["emr-versioning"]
)
api_router.include_router(
    emr_lab_integration.router, prefix="/emr/lab", tags=["emr-lab-integration"]
)
api_router.include_router(emr_export.router, prefix="/emr/export", tags=["emr-export"])
api_router.include_router(
    advanced_analytics.router, prefix="/analytics/advanced", tags=["advanced-analytics"]
)
api_router.include_router(
    analytics_export.router, prefix="/analytics/export", tags=["analytics-export"]
)
api_router.include_router(
    analytics_visualization.router,
    prefix="/analytics/visualization",
    tags=["analytics-visualization"],
)
api_router.include_router(
    two_factor_auth.router, prefix="/2fa", tags=["two-factor-auth"]
)
api_router.include_router(
    two_factor_sms_email.router, prefix="/2fa", tags=["two-factor-sms-email"]
)
api_router.include_router(
    two_factor_devices.router, prefix="/2fa", tags=["two-factor-devices"]
)
api_router.include_router(sms_providers.router, prefix="/sms", tags=["sms-providers"])
api_router.include_router(
    telegram_webhook.router, prefix="/telegram", tags=["telegram-webhook"]
)
api_router.include_router(
    telegram_webhook_enhanced.router,
    prefix="/telegram",
    tags=["telegram-webhook-enhanced"],
)
api_router.include_router(
    telegram_notifications.router, prefix="/telegram", tags=["telegram-notifications"]
)
api_router.include_router(
    telegram_bot_management.router,
    prefix="/telegram-bot",
    tags=["telegram-bot-management"],
)
api_router.include_router(
    fcm_notifications.router, prefix="/fcm", tags=["fcm-notifications"]
)
api_router.include_router(
    phone_verification.router, prefix="/phone-verification", tags=["phone-verification"]
)
api_router.include_router(
    password_reset.router, prefix="/password-reset", tags=["password-reset"]
)
# Эндпоинты переупорядочения очереди (специализированный функционал)
api_router.include_router(
    queue_reorder.router, prefix="/queue/reorder", tags=["queue-reorder"]
)
api_router.include_router(
    websocket_auth.router, prefix="/ws-auth", tags=["websocket-auth"]
)
api_router.include_router(
    email_sms_enhanced.router, prefix="/email-sms", tags=["email-sms-enhanced"]
)
api_router.include_router(file_system.router, prefix="/files", tags=["file-system"])
api_router.include_router(
    file_upload_simple.router, prefix="/files", tags=["file-upload-simple"]
)
api_router.include_router(
    file_upload_json.router, prefix="/files", tags=["file-upload-json"]
)
api_router.include_router(file_test.router, prefix="/files", tags=["file-test"])
api_router.include_router(schedule.router, tags=["schedule"])
# Legacy queue router (для обратной совместимости)
# ⚠️ DEPRECATED: Используйте /queue/qr-tokens/* или /queue/join/* из qr_queue.py
api_router.include_router(queue_router, prefix="/queue/legacy", tags=["queue-legacy"])
api_router.include_router(cardio.router, tags=["cardio"])
api_router.include_router(derma.router, tags=["derma"])
api_router.include_router(dental.router, tags=["dental"])
api_router.include_router(lab_specialized.router, tags=["lab_specialized"])
api_router.include_router(
    appointment_flow.router, prefix="/appointments", tags=["appointment_flow"]
)
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(
    analytics_kpi.router, prefix="/analytics", tags=["analytics-kpi"]
)
api_router.include_router(
    analytics_predictive.router, prefix="/analytics", tags=["analytics-predictive"]
)
api_router.include_router(
    notifications.router, prefix="/notifications", tags=["notifications"]
)
api_router.include_router(docs.router, prefix="/docs", tags=["documentation"])
api_router.include_router(
    api_documentation.router, prefix="/documentation", tags=["api-docs"]
)
api_router.include_router(
    specialized_panels.router, prefix="/specialized", tags=["specialized-panels"]
)
api_router.include_router(health_ep.router, tags=["health"])
api_router.include_router(activation_ep.router, tags=["activation"])
api_router.include_router(
    authentication.router, prefix="/authentication", tags=["authentication"]
)
api_router.include_router(
    user_management.router, prefix="/users", tags=["user-management"]
)

# Legacy API удалён - используйте /api/v1/queue/* endpoints

# Автозакрытие очередей
from app.api.v1.endpoints import queue_auto_close

api_router.include_router(
    queue_auto_close.router, prefix="/admin/queue-auto-close", tags=["queue-auto-close"]
)

# Облачная печать
api_router.include_router(
    cloud_printing.router, prefix="/cloud-printing", tags=["cloud-printing"]
)

# Медицинское оборудование
api_router.include_router(
    medical_equipment.router, prefix="/medical-equipment", tags=["medical-equipment"]
)

# Динамическое ценообразование
api_router.include_router(
    dynamic_pricing.router, prefix="/dynamic-pricing", tags=["dynamic-pricing"]
)

# Автоматическое выставление счетов
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])

# Система скидок и льгот
api_router.include_router(
    discount_benefits.router, prefix="/discount-benefits", tags=["discount-benefits"]
)
