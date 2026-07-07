"""
NOTIF-REAUDIT-28 P1: notification_service.py was a 400-LOC duplicate of
notifications.py with a mock SMS stub (_send_sms returned success without
sending). Replaced with a thin re-export for backward compatibility.

Callers should migrate to:
    from app.services.notifications import notification_sender_service
"""
from app.services.notifications import NotificationSenderService as NotificationService
from app.services.notifications import notification_sender_service

__all__ = ["NotificationService", "notification_sender_service"]
