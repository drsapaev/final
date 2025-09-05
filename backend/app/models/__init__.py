from __future__ import annotations

# Package marker for app.models

# Import all models to ensure they are registered with SQLAlchemy
from .user import User
from .patient import Patient  
from .visit import Visit, VisitService
from .service import Service, ServiceCatalog
from .payment import Payment
from .payment_webhook import PaymentWebhook, PaymentProvider, PaymentTransaction
from .appointment import Appointment
from .queue import QueueTicket
from .schedule import ScheduleTemplate
from .emr import EMR, Prescription
from .lab import LabOrder, LabResult
from .audit import AuditLog
from .notification import NotificationTemplate, NotificationHistory, NotificationSettings
from .setting import Setting
from .activation import Activation
from .online import OnlineDay
from .clinic import ClinicSettings, Doctor, Schedule, ServiceCategory

# Make sure all models are available
__all__ = [
    "User",
    "Patient", 
    "Visit",
    "VisitService",
    "Service",
    "ServiceCatalog", 
    "Payment",
    "PaymentWebhook",
    "PaymentProvider",
    "PaymentTransaction",
    "Appointment",
    "QueueTicket",
    "ScheduleTemplate",
    "EMR",
    "Prescription",
    "LabOrder",
    "LabResult",
    "AuditLog",
    "NotificationTemplate",
    "NotificationHistory", 
    "NotificationSettings",
    "Setting",
    "Activation",
    "OnlineDay",
    "ClinicSettings",
    "Doctor",
    "Schedule",
    "ServiceCategory",
]
