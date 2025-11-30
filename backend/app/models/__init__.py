from __future__ import annotations

from .activation import Activation
from .appointment import Appointment
from .audit import AuditLog
from .authentication import (
    EmailVerificationToken,
    LoginAttempt,
    PasswordResetToken,
    RefreshToken,
    SecurityEvent,
    UserActivity,
    UserSession,
)
from .clinic import (
    Backup,
    BackupStatus,
    BackupType,
    Branch,
    BranchStatus,
    ClinicSettings,
    Doctor,
    Equipment,
    EquipmentMaintenance,
    EquipmentStatus,
    EquipmentType,
    License,
    LicenseActivation,
    LicenseStatus,
    LicenseType,
    Schedule,
    ServiceCategory,
    SystemInfo,
)
from .department import (
    Department,
    DepartmentQueueSettings,
    DepartmentRegistrationSettings,
    DepartmentService,
)
from .doctor_price_override import DoctorPriceOverride
from .emr import EMR, Prescription
from .emr_template import EMRTemplate
from .emr_version import EMRVersion
from .file_system import (
    File,
    FileAccessLog,
    FileFolder,
    FilePermission,
    FileQuota,
    FileShare,
    FileStatus,
    FileStorage,
    FileType,
    FileVersion,
)

# КРИТИЧЕСКИ ВАЖНО: UserGroup и связанные модели ТОЛЬКО из role_permission.py!
from .lab import LabOrder, LabResult
from .notification import (
    NotificationHistory,
    NotificationSettings,
    NotificationTemplate,
)
from .online import OnlineDay
from .online_queue import DailyQueue, OnlineQueueEntry, QueueToken
from .patient import Patient
from .payment import Payment
from .payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from .payment_webhook import PaymentProvider, PaymentTransaction, PaymentWebhook
from .role_permission import Permission, Role, UserGroup, UserPermissionOverride

# Временно отключены из-за проблем с relationships
# from .payment_invoice import PaymentInvoice, PaymentInvoiceVisit
# from .billing import Invoice, InvoiceItem, BillingPayment, InvoiceTemplate, BillingRule, PaymentReminder
# from .discount_benefits import Discount, Benefit, LoyaltyProgram
# from .dynamic_pricing import PricingRule, ServicePackage, PackagePurchase
# from .emr import EMR, Prescription
# from .emr_template import EMRTemplate
# from .emr_version import EMRVersion
# from .two_factor_auth import TwoFactorAuth, TwoFactorBackupCode, TwoFactorRecovery, TwoFactorSession, TwoFactorDevice
# from .user_profile import UserProfile, UserPreferences, UserNotificationSettings, UserAuditLog
# from .role_permission import Role, Permission, UserRole, UserGroup, GroupRole, UserPermissionOverride, RoleHierarchy, PermissionAuditLog
# from .authentication import UserSession, RefreshToken, PasswordResetToken, EmailVerificationToken, LoginAttempt, UserActivity, SecurityEvent
# from .clinic import ClinicSettings, Branch, License, Backup, SystemInfo, Equipment, EquipmentMaintenance
# from .file_system import FileStorage, FileFolder, FileQuota, File, FileAccessLog, FileShare, FileVersion
# from .queue_new import QueueEntry, QueueToken, QueueStatistics
# from .queue_old import QueueTicket
# from .online_queue import OnlineQueueEntry, OnlineQueueToken
# from .schedule import ScheduleTemplate
# from .doctor_price_override import DoctorPriceOverride
# from .webhook import Webhook, WebhookCall, WebhookEvent
# from .ai_config import AIProvider, AIProviderSettings
# from .display_config import DisplayBoard, DisplayBanner, DisplayTheme
# from .print_config import PrintTemplate, PrintJob
# from .dermatology_photos import DermatologyPhoto
# from .telegram import TelegramConfig, TelegramUser, TelegramMessage, TelegramTemplate
# from .notification import NotificationTemplate, NotificationHistory, NotificationSettings
# from .payment import Payment
# from .payment_webhook import PaymentWebhook, PaymentProvider, PaymentTransaction
# QueueTicket заменен на новые модели в queue.py
from .schedule import ScheduleTemplate
from .service import Service, ServiceCatalog
from .setting import Setting
from .telegram_config import (
    TelegramConfig,
    TelegramMessage,
    TelegramTemplate,
    TelegramUser,
)
from .two_factor_auth import (
    TwoFactorAuth,
    TwoFactorBackupCode,
    TwoFactorDevice,
    TwoFactorRecovery,
    TwoFactorSession,
)

# Import all models to ensure they are registered with SQLAlchemy
from .user import User
from .user_profile import (
    UserAuditLog,
    UserNotificationSettings,
    UserPreferences,
    UserProfile,
)
from .visit import Visit, VisitService

# Package marker for app.models


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
    # "QueueTicket", # заменен на DailyQueue, QueueEntry, QueueToken
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
    "UserAuditLog",
    # Роли и разрешения ТОЛЬКО из role_permission.py:
    "Role",
    "Permission",
    "UserGroup",
    "UserPermissionOverride",
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
    "OnlineQueueEntry",
    "QueueToken",
    "TelegramConfig",
    "TelegramTemplate",
    "TelegramUser",
    "TelegramMessage",
    "DoctorPriceOverride",
    "PaymentInvoice",
    "PaymentInvoiceVisit",
    "Department",
    "DepartmentService",
    "DepartmentQueueSettings",
    "DepartmentRegistrationSettings",
]
