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
from .emr_template import EMRTemplate
from .emr_version import EMRVersion
from .two_factor_auth import TwoFactorAuth, TwoFactorBackupCode, TwoFactorRecovery, TwoFactorSession, TwoFactorDevice
from .authentication import RefreshToken, UserSession, PasswordResetToken, EmailVerificationToken, LoginAttempt, UserActivity, SecurityEvent
from .user_profile import (
    UserProfile, UserPreferences, UserNotificationSettings, UserRole, UserPermission,
    RolePermission, UserGroup, UserGroupMember, UserAuditLog
)
from .lab import LabOrder, LabResult
from .audit import AuditLog
from .notification import NotificationTemplate, NotificationHistory, NotificationSettings
from .setting import Setting
from .activation import Activation
from .online import OnlineDay
from .clinic import (
    ClinicSettings, Doctor, Schedule, ServiceCategory, Branch, BranchStatus,
    Equipment, EquipmentStatus, EquipmentType, EquipmentMaintenance,
    License, LicenseStatus, LicenseType, LicenseActivation,
    Backup, BackupStatus, BackupType, SystemInfo
)
from .online_queue import DailyQueue, QueueEntry, QueueToken

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
    "EMRTemplate",
    "EMRVersion",
    "TwoFactorAuth",
    "TwoFactorBackupCode", 
    "TwoFactorRecovery",
    "TwoFactorSession",
    "TwoFactorDevice",
    "RefreshToken",
    "UserSession",
    "PasswordResetToken",
    "EmailVerificationToken",
    "LoginAttempt",
    "UserActivity",
    "SecurityEvent",
    "UserProfile",
    "UserPreferences",
    "UserNotificationSettings",
    "UserRole",
    "UserPermission",
    "RolePermission",
    "UserGroup",
    "UserGroupMember",
    "UserAuditLog",
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
    "Branch",
    "BranchStatus",
    "Equipment",
    "EquipmentStatus",
    "EquipmentType",
    "EquipmentMaintenance",
    "License",
    "LicenseStatus",
    "LicenseType",
    "LicenseActivation",
    "Backup",
    "BackupStatus",
    "BackupType",
    "SystemInfo",
    "DailyQueue",
    "QueueEntry", 
    "QueueToken",
]
