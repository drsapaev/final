# app/api/v1/api.py
from __future__ import annotations

import logging

from fastapi import APIRouter

from app.api.v1.endpoints import (
    activation as activation_ep,
)
from app.api.v1.endpoints import (
    admin_ai,
    admin_clinic,
    admin_departments,
    admin_display,
    admin_doctors,
    admin_providers,
    admin_stats,
    admin_telegram,
    admin_users,
    advanced_analytics,
    ai,
    ai_analytics,
    ai_chat,
    ai_cost_analytics,
    ai_gateway,
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
    billing,
    board_display_state,
    cardio,
    cashier,
    clinic_management,
    cloud_printing,
    dental,
    departments,
    derma,
    discount_benefits,
    display_websocket,
    docs,
    doctor_info,
    doctor_integration,
    doctor_templates,
    dynamic_pricing,
    email_sms_enhanced,
    emr_ai,
    emr_ai_enhanced,
    emr_export,
    emr_lab_integration,
    emr_templates,
    emr_v2,
    emr_versioning_enhanced,
    fcm_notifications,
    feature_flags,
    file_system,
    file_test,
    file_upload_json,
    file_upload_simple,
    force_majeure,
    global_search,
    group_permissions,
    lab,
    lab_specialized,
    medical_equipment,
    messages,
    minimal_auth,
    mobile_api,
    mobile_api_extended,
    notification_websocket,
    notifications,
    observability,
    online_queue_new,
    password_reset,
    patients,
    payment_reconciliation,
    payment_settings,
    payment_webhook,
    payments,
    phone_verification,
    phrase_suggest,
    print_api,
    print_templates,
    qr_queue,
    queue_auto_close,
    queue_cabinet_management,
    queue_limits,
    queue_position,
    queue_reorder,
    queues,
    registrar_batch,
    registrar_integration,
    registrar_notifications,
    registrar_wizard,
    reports,
    roles,
    schedule,
    services,
    simple_auth,
    sms_providers,
    specialized_panels,
    system_management,
    telegram_bot,
    telegram_bot_management,
    telegram_integration,
    telegram_notifications,
    telegram_webhook,
    telegram_webhook_enhanced,
    telemetry,
    two_factor_auth,
    two_factor_devices,
    two_factor_sms_email,
    user_data_transfer,
    user_management,
    utils,
    visits,
    wait_time_analytics,
    webhooks,
    websocket_auth,
)
from app.api.v1.endpoints import (
    board as board_ep,
)
from app.api.v1.endpoints import (
    health as health_ep,
)
from app.api.v1.endpoints import (
    print as print_ep,
)
from app.api.v1.endpoints import (
    reports as reports_ep,
)
from app.api.v1.endpoints.migration_management import (
    router as migration_management_router,
)
from app.api.v1.endpoints.morning_assignment import router as morning_assignment_router
from app.api.v1.endpoints.payment_webhooks import router as payment_webhooks_router
from app.api.v1.endpoints.queue import router as queue_router
from app.api.v1.endpoints.section_templates import router as section_templates_router
from app.api.v1.endpoints.security_management import (
    router as security_management_router,
)
from app.api.v1.endpoints.visit_confirmation import router as visit_confirmation_router
from app.ws import cashier_ws

try:
    from app.api.v1.endpoints import mcp
except ImportError:
    mcp = None

logger = logging.getLogger(__name__)

api_router = APIRouter()

# Auth (/login, /me и т.д.)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

api_router.include_router(simple_auth.router, prefix="/auth", tags=["simple-auth"])

api_router.include_router(minimal_auth.router, prefix="/auth", tags=["minimal-auth"])
api_router.include_router(patients.router, prefix="/patients", tags=["patients"])
api_router.include_router(visits.router, prefix="/visits", tags=["visits"])
api_router.include_router(services.router, prefix="/services")
api_router.include_router(
    departments.router, prefix="/departments", tags=["departments"]
)
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
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
# Эндпоинты универсальных секционных шаблонов врача (Мой опыт)
api_router.include_router(
    section_templates_router,
    tags=["section-templates"],
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
api_router.include_router(online_queue_new.router, tags=["online-queue-new"])
api_router.include_router(registrar_integration.router, tags=["registrar"])
api_router.include_router(registrar_wizard.router, tags=["registrar-wizard"])
api_router.include_router(doctor_integration.router, tags=["doctor-integration"])
api_router.include_router(
    print_templates.router, prefix="/print/templates", tags=["print-templates"]
)
api_router.include_router(print_api.router, prefix="/print", tags=["print-api"])
api_router.include_router(ai_integration.router, prefix="/ai", tags=["ai-integration"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])  # Новые AI endpoints

api_router.include_router(ai_gateway.router, prefix="/ai/v2", tags=["ai-gateway"])

api_router.include_router(ai_chat.router, prefix="/ai/chat", tags=["ai-chat"])

api_router.include_router(ai_cost_analytics.router, prefix="/ai/analytics", tags=["ai-cost-analytics"])


# MCP (Model Context Protocol) endpoints
if mcp:
    api_router.include_router(mcp.router, prefix="/mcp", tags=["mcp"])
else:
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
api_router.include_router(board_display_state.router, tags=["board-display"])
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
# Doctor Treatment Templates - персональная клиническая память
api_router.include_router(
    doctor_templates.router, prefix="/emr", tags=["doctor-templates"]
)
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
api_router.include_router(lab.router, tags=["lab"])
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
api_router.include_router(
    notification_websocket.router, tags=["notification-websocket"]
)
api_router.include_router(docs.router, prefix="/docs", tags=["documentation"])
api_router.include_router(
    api_documentation.router, prefix="/documentation", tags=["api-docs"]
)
api_router.include_router(
    specialized_panels.router, prefix="/specialized", tags=["specialized-panels"]
)
api_router.include_router(health_ep.router, tags=["health"])
api_router.include_router(observability.router, tags=["observability"])
api_router.include_router(activation_ep.router, tags=["activation"])
api_router.include_router(
    authentication.router, prefix="/authentication", tags=["authentication"]
)
api_router.include_router(
    user_management.router, prefix="/users", tags=["user-management"]
)

# Роли и разрешения
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])

# Legacy API удалён - используйте /api/v1/queue/* endpoints

# Автозакрытие очередей
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

# Эндпоинты для кассира
api_router.include_router(cashier.router, prefix="/cashier", tags=["cashier"])

# WebSocket для кассира (real-time updates)
api_router.include_router(cashier_ws.router, prefix="/ws", tags=["cashier-ws"])

# Форс-мажор (массовый перенос/отмена очереди с возвратами)
api_router.include_router(
    force_majeure.router, prefix="/force-majeure", tags=["force-majeure"]
)

# Push-уведомления о позиции в очереди
api_router.include_router(
    queue_position.router, prefix="/queue/position", tags=["queue-position"]
)

# Batch операции с записями пациентов (UI Row ↔ API Entry)
api_router.include_router(
    registrar_batch.router, prefix="/registrar", tags=["registrar-batch"]
)

# EMR Phrase Suggest - автоподсказки из истории врача
api_router.include_router(
    phrase_suggest.router, prefix="/emr", tags=["emr-phrase-suggest"]
)

# EMR v2 - Production EMR with versioning and audit
api_router.include_router(
    emr_v2.router, prefix="/v2", tags=["emr-v2"]
)

# Global Search - агрегированный поиск по всем доменам
api_router.include_router(
    global_search.router, tags=["global-search"]
)

# Telemetry - Product metrics (NO PHI, events only)
api_router.include_router(
    telemetry.router, tags=["telemetry"]
)

# User-to-user messaging system
api_router.include_router(
    messages.router, prefix="/messages", tags=["messages"]
)

# Utils (Link preview, etc.)
api_router.include_router(
    utils.router, prefix="/utils", tags=["utils"]
)
