# app/api/v1/api.py
from __future__ import annotations

from fastapi import APIRouter

# подключаем router из каждого модуля
from app.api.v1.endpoints import (
    activation as activation_ep,
    admin_ai,
    admin_clinic,
    clinic_management,
    admin_display,
    admin_doctors,
    admin_providers,
    admin_stats,
    admin_telegram,
    admin_users,
    ai,  # Новый AI модуль
    analytics,
    telegram_bot,  # Telegram Bot
    payment_settings,  # Настройки платежных провайдеров
    analytics_kpi,
    analytics_predictive,
    api_documentation,
    appointment_flow,
    appointments,
    auth,
    board as board_ep,
    cardio,
    dental,
    feature_flags,  # Фича-флаги
    qr_queue,  # QR очереди
    derma,
    docs,
    health as health_ep,
    lab_specialized,
    mobile_api,
    notifications,
    emr_templates,
    emr_ai,
    emr_ai_enhanced,
    emr_versioning_enhanced,
    emr_lab_integration,
    emr_export,
    advanced_analytics,
    analytics_export,
    analytics_visualization,
    two_factor_auth,
    two_factor_sms_email,
    two_factor_devices,
    telegram_webhook,
    telegram_notifications,
    email_sms_enhanced,
    file_system,
    file_upload_simple,
    file_upload_json,
    file_test,
    authentication,
    user_management,
    # online_queue,  # Временно отключено
    # online_queue_new,  # Временно отключено
    patients,
    registrar_integration,
    registrar_wizard,  # Новый мастер регистрации
    doctor_integration,
    print_templates,
    print_api,
    ai_integration,
    telegram_integration,
    display_websocket,
    payment_webhook,
    payments,
    print as print_ep,
    # queue,  # Временно отключено
    queues,
    reports as reports_ep,
    schedule,
    services,
    specialized_panels,
    visits,
)
# Импортируем новый queue endpoint
from app.api.v1.endpoints.queue import router as queue_router
from app.api.v1.endpoints.queue_simple import router as simple_queue_router
# from app.api.v1.endpoints.queue_fixed import router as fixed_queue_router  # Временно отключено

# Импортируем новые payment endpoints
from app.api.v1.endpoints.payments import router as payments_new_router
from app.api.v1.endpoints.payment_webhooks import router as payment_webhooks_router

# Импортируем эндпоинты подтверждения визитов
from app.api.v1.endpoints.visit_confirmation import router as visit_confirmation_router

# Импортируем эндпоинты утренней сборки
from app.api.v1.endpoints.morning_assignment import router as morning_assignment_router

# Импортируем эндпоинты управления безопасностью
from app.api.v1.endpoints.security_management import router as security_management_router

# Импортируем эндпоинты управления миграциями
from app.api.v1.endpoints.migration_management import router as migration_management_router

api_router = APIRouter()

# Auth (/login, /me и т.д.)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(patients.router, prefix="/patients", tags=["patients"])
api_router.include_router(visits.router, prefix="/visits", tags=["visits"])
api_router.include_router(services.router, prefix="/services")
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(payments_new_router, prefix="/payments", tags=["payments-new"])
api_router.include_router(payment_webhooks_router, prefix="/payments/webhook", tags=["payment-webhooks"])

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
# Эндпоинты QR очередей
api_router.include_router(qr_queue.router, tags=["qr-queue"])
api_router.include_router(queues.router, prefix="/queues", tags=["queues"])
api_router.include_router(appointments.router, tags=["appointments"])
# api_router.include_router(online_queue.router, tags=["online-queue"])  # Временно отключено
# api_router.include_router(online_queue_new.router, tags=["online-queue-new"])  # Временно отключено
api_router.include_router(registrar_integration.router, tags=["registrar"])
api_router.include_router(registrar_wizard.router, tags=["registrar-wizard"])
api_router.include_router(doctor_integration.router, tags=["doctor-integration"])
api_router.include_router(print_templates.router, prefix="/print/templates", tags=["print-templates"])
api_router.include_router(print_api.router, prefix="/print", tags=["print-api"])
api_router.include_router(ai_integration.router, prefix="/ai", tags=["ai-integration"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])  # Новые AI endpoints
api_router.include_router(telegram_bot.router, prefix="/telegram/bot", tags=["telegram-bot"])  # Telegram Bot
api_router.include_router(telegram_integration.router, prefix="/telegram", tags=["telegram-integration"])
api_router.include_router(display_websocket.router, prefix="/display", tags=["display-websocket"])
api_router.include_router(print_ep.router, tags=["print"])
api_router.include_router(board_ep.router, tags=["board"])
api_router.include_router(reports_ep.router, tags=["reports"])
api_router.include_router(payment_webhook.router, tags=["webhooks"])
api_router.include_router(admin_ai.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_clinic.router, prefix="/admin", tags=["admin"])
api_router.include_router(clinic_management.router, prefix="/clinic", tags=["clinic-management"])
api_router.include_router(payment_settings.router, tags=["payment-settings"])
api_router.include_router(admin_display.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_doctors.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_providers.router, tags=["admin"])
api_router.include_router(admin_telegram.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_stats.router, tags=["admin"])
api_router.include_router(admin_users.router)
api_router.include_router(mobile_api.router, prefix="/mobile", tags=["mobile"])
api_router.include_router(emr_templates.router, prefix="/emr", tags=["emr-templates"])
api_router.include_router(emr_ai.router, prefix="/emr/ai", tags=["emr-ai"])
api_router.include_router(emr_ai_enhanced.router, prefix="/emr/ai-enhanced", tags=["emr-ai-enhanced"])
api_router.include_router(emr_versioning_enhanced.router, prefix="/emr/versions", tags=["emr-versioning"])
api_router.include_router(emr_lab_integration.router, prefix="/emr/lab", tags=["emr-lab-integration"])
api_router.include_router(emr_export.router, prefix="/emr/export", tags=["emr-export"])
api_router.include_router(advanced_analytics.router, prefix="/analytics/advanced", tags=["advanced-analytics"])
api_router.include_router(analytics_export.router, prefix="/analytics/export", tags=["analytics-export"])
api_router.include_router(analytics_visualization.router, prefix="/analytics/visualization", tags=["analytics-visualization"])
api_router.include_router(two_factor_auth.router, prefix="/2fa", tags=["two-factor-auth"])
api_router.include_router(two_factor_sms_email.router, prefix="/2fa", tags=["two-factor-sms-email"])
api_router.include_router(two_factor_devices.router, prefix="/2fa", tags=["two-factor-devices"])
api_router.include_router(telegram_webhook.router, prefix="/telegram", tags=["telegram-webhook"])
api_router.include_router(telegram_notifications.router, prefix="/telegram", tags=["telegram-notifications"])
api_router.include_router(email_sms_enhanced.router, prefix="/email-sms", tags=["email-sms-enhanced"])
api_router.include_router(file_system.router, prefix="/files", tags=["file-system"])
api_router.include_router(file_upload_simple.router, prefix="/files", tags=["file-upload-simple"])
api_router.include_router(file_upload_json.router, prefix="/files", tags=["file-upload-json"])
api_router.include_router(file_test.router, prefix="/files", tags=["file-test"])
api_router.include_router(schedule.router, tags=["schedule"])
# Основной queue router с онлайн-очередью
api_router.include_router(queue_router, prefix="/queue", tags=["queue"])
# Простой queue router для тестирования
api_router.include_router(simple_queue_router, prefix="/queue", tags=["queue-simple"])
# Исправленный queue router (временно отключено)
# api_router.include_router(fixed_queue_router, prefix="/queue", tags=["queue-fixed"])
api_router.include_router(cardio.router, tags=["cardio"])
api_router.include_router(derma.router, tags=["derma"])
api_router.include_router(dental.router, tags=["dental"])
api_router.include_router(lab_specialized.router, tags=["lab_specialized"])
api_router.include_router(
    appointment_flow.router, prefix="/appointments", tags=["appointment_flow"]
)
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(analytics_kpi.router, prefix="/analytics", tags=["analytics-kpi"])
api_router.include_router(analytics_predictive.router, prefix="/analytics", tags=["analytics-predictive"])
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
api_router.include_router(authentication.router, prefix="/authentication", tags=["authentication"])
api_router.include_router(user_management.router, prefix="/users", tags=["user-management"])

# Legacy API для совместимости с документацией
from app.api.v1.endpoints import online_queue_legacy
api_router.include_router(online_queue_legacy.router, prefix="/online-queue", tags=["online-queue-legacy"])

# Автозакрытие очередей
from app.api.v1.endpoints import queue_auto_close
api_router.include_router(queue_auto_close.router, prefix="/admin/queue-auto-close", tags=["queue-auto-close"])
