"""
I18N-AUDIT: Internationalization constants for service-layer messages.

Currently Russian (ru) is hardcoded throughout the service layer.
This module provides a translation lookup for common messages.
Future: wire into a proper i18n framework (gettext, babel, fluent).

Usage:
    from app.core.i18n import t
    message = t("error.internal", "ru")  # → "Внутренняя ошибка сервера"
    message = t("error.internal", "uz")  # → "Ichki server xatosi"
"""
from __future__ import annotations

# Translation table: key → {language_code: translated_string}
TRANSLATIONS = {
    "error.internal": {
        "ru": "Внутренняя ошибка сервера",
        "uz": "Ichki server xatosi",
        "en": "Internal server error",
    },
    "error.not_found": {
        "ru": "Запись не найдена",
        "uz": "Yozuv topilmadi",
        "en": "Record not found",
    },
    "error.access_denied": {
        "ru": "Доступ запрещён",
        "uz": "Kirish rad etildi",
        "en": "Access denied",
    },
    "error.validation": {
        "ru": "Ошибка валидации",
        "uz": "Validatsiya xatosi",
        "en": "Validation error",
    },
    "error.payment_failed": {
        "ru": "Ошибка платежа",
        "uz": "To'lov xatosi",
        "en": "Payment failed",
    },
    "error.queue_full": {
        "ru": "Очередь заполнена",
        "uz": "Navbat to'la",
        "en": "Queue is full",
    },
    "error.already_exists": {
        "ru": "Запись уже существует",
        "uz": "Yozuv allaqachon mavjud",
        "en": "Record already exists",
    },
    "error.token_invalid": {
        "ru": "Недействительный токен",
        "uz": "Noto'g'ri token",
        "en": "Invalid token",
    },
    "error.token_expired": {
        "ru": "Срок действия токена истёк",
        "uz": "Token muddati tugagan",
        "en": "Token expired",
    },
    "success.saved": {
        "ru": "Сохранено успешно",
        "uz": "Muvaffaqiyatli saqlandi",
        "en": "Saved successfully",
    },
    "success.deleted": {
        "ru": "Удалено успешно",
        "uz": "Muvaffaqiyatli o'chirildi",
        "en": "Deleted successfully",
    },
    "success.created": {
        "ru": "Создано успешно",
        "uz": "Muvaffaqiyatli yaratildi",
        "en": "Created successfully",
    },
    "success.updated": {
        "ru": "Обновлено успешно",
        "uz": "Muvaffaqiyatli yangilandi",
        "en": "Updated successfully",
    },
    "patient.not_found": {
        "ru": "Пациент не найден",
        "uz": "Bemor topilmadi",
        "en": "Patient not found",
    },
    "doctor.not_found": {
        "ru": "Врач не найден",
        "uz": "Shifokor topilmadi",
        "en": "Doctor not found",
    },
    "visit.not_found": {
        "ru": "Визит не найден",
        "uz": "Tashrif topilmadi",
        "en": "Visit not found",
    },
}

DEFAULT_LANGUAGE = "ru"


def t(key: str, language: str | None = None) -> str:
    """Translate a key to the specified language.

    Falls back to Russian (default), then to the key itself.
    """
    lang = language or DEFAULT_LANGUAGE
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    return entry.get(lang) or entry.get(DEFAULT_LANGUAGE) or key


def supported_languages() -> list[str]:
    """Return list of supported language codes."""
    return ["ru", "uz", "en"]
