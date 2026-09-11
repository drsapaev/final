"""
Pydantic схемы для онлайн-очереди согласно detail.md
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ===================== QR ТОКЕНЫ =====================


class QRTokenRequest(BaseModel):
    """Запрос на генерацию QR токена"""

    day: date = Field(..., description="Дата в формате YYYY-MM-DD")
    specialist_id: int = Field(..., description="ID врача/специалиста")


class QRTokenResponse(BaseModel):
    """Ответ с QR токеном"""

    token: str = Field(..., description="Уникальный токен для QR")
    qr_url: str = Field(..., description="URL для QR кода")
    specialist_name: str = Field(..., description="Имя специалиста")
    specialty: str = Field(..., description="Специальность")
    cabinet: str | None = Field(None, description="Номер кабинета")
    day: date = Field(..., description="Дата приема")
    start_time: str = Field(..., description="Время начала онлайн-записи")
    max_slots: int = Field(..., description="Максимум мест в очереди")
    current_count: int = Field(0, description="Текущее количество записавшихся")


# ===================== ВСТУПЛЕНИЕ В ОЧЕРЕДЬ =====================


class QueueJoinRequest(BaseModel):
    """Запрос на вступление в очередь"""

    token: str = Field(..., description="Токен из QR кода")
    phone: str | None = Field(None, description="Номер телефона")
    telegram_id: int | None = Field(None, description="ID Telegram чата")
    patient_name: str | None = Field(None, description="Имя пациента")


class QueueJoinResponse(BaseModel):
    """Ответ на вступление в очередь"""

    success: bool = Field(..., description="Успешность операции")
    number: int | None = Field(None, description="Номер в очереди")
    duplicate: bool = Field(False, description="Повторная запись (тот же номер)")
    message: str = Field(..., description="Сообщение пользователю")

    # Дополнительная информация
    specialist_name: str | None = None
    cabinet: str | None = None
    estimated_time: str | None = None  # Примерное время приема


class QueueJoinError(BaseModel):
    """Ошибка вступления в очередь"""

    success: bool = Field(False)
    error_code: str = Field(..., description="Код ошибки")
    message: str = Field(..., description="Сообщение об ошибке")

    # Дополнительная информация
    queue_closed: bool = Field(False, description="Очередь закрыта")
    queue_full: bool = Field(False, description="Очередь переполнена")
    outside_hours: bool = Field(False, description="Вне рабочих часов")


# ===================== ОТКРЫТИЕ ПРИЕМА =====================


class QueueOpenRequest(BaseModel):
    """Запрос на открытие приема"""

    day: date = Field(..., description="Дата")
    specialist_id: int = Field(..., description="ID специалиста")


class QueueOpenResponse(BaseModel):
    """Ответ на открытие приема"""

    success: bool = Field(..., description="Успешность операции")
    message: str = Field(..., description="Сообщение")
    opened_at: datetime = Field(..., description="Время открытия")
    online_entries_count: int = Field(..., description="Количество онлайн-записей")
    closed_online_registration: bool = Field(..., description="Онлайн-набор закрыт")


# ===================== СОСТОЯНИЕ ОЧЕРЕДИ =====================


class QueueEntryOut(BaseModel):
    """Запись в очереди"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    number: int
    patient_name: str | None = None
    phone: str | None = None
    source: str
    status: str
    created_at: datetime
    called_at: datetime | None = None


class DailyQueueOut(BaseModel):
    """Состояние дневной очереди"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    day: date
    # QD-2A (dual-owner expand): specialist_id теперь nullable — у
    # ресурсной очереди врач-владелец отступает, владелец живёт в
    # queue_resource_id.
    # QD-2C (runtime switch, output contract): добавлены owner_kind
    # («doctor» | «resource» — какая ось владеет очередью),
    # owner_display_name (человекочитаемый владелец) и краткий объект
    # queue_resource. Выводимая ось вычисляется из сохранённых полей
    # (queue_resource_id установлен — ресурс; иначе врач).
    specialist_id: int | None = None
    queue_resource_id: int | None = None
    owner_kind: Literal["doctor", "resource"] | None = None
    owner_display_name: str | None = None
    queue_resource: dict | None = None
    active: bool
    opened_at: datetime | None = None
    created_at: datetime

    # Связанные данные
    specialist: dict | None = None
    entries: list[QueueEntryOut] = []

    # Статистика
    total_entries: int = 0
    waiting_count: int = 0
    served_count: int = 0

    @model_validator(mode="before")
    @classmethod
    def _qd2c_coerce_orm(cls, data: object) -> object:
        """ORM-гидрация (from_attributes): связи specialist /
        queue_resource — ORM-объекты, а поля схемы — dict;
        конвертируем до валидации (врач — в None: полная карточка
        врача отдаётся полем specialist только явными билдерами).
        """
        if isinstance(data, dict) or data is None:
            return data
        queue = data
        fields = {
            "id": queue.id,
            "day": queue.day,
            "specialist_id": queue.specialist_id,
            "queue_resource_id": queue.queue_resource_id,
            "active": queue.active,
            "opened_at": queue.opened_at,
            "created_at": queue.created_at,
        }
        resource = getattr(queue, "queue_resource", None)
        if resource is not None:
            fields["queue_resource"] = {
                "id": resource.id,
                "code": resource.code,
                "queue_tag": resource.queue_tag,
                "display_name": resource.display_name,
            }
            fields["owner_display_name"] = resource.display_name
        return fields

    @model_validator(mode="after")
    def _resolve_qd2c_owner_fields(self) -> "DailyQueueOut":
        """QD-2C output contract: ось владения выводится из полей
        строки (queue_resource_id установлен — ресурс; иначе врач).
        Явно переданные значения не перезаписываются."""
        if self.owner_kind is None:
            self.owner_kind = "resource" if self.queue_resource_id else "doctor"
        if self.queue_resource_id and self.queue_resource is None:
            self.queue_resource = {"id": self.queue_resource_id}
        return self


# ===================== НАСТРОЙКИ ОЧЕРЕДИ =====================


class QueueSettings(BaseModel):
    """Настройки очереди из админ панели"""

    timezone: str = Field("Asia/Tashkent", description="Часовой пояс")
    queue_start_hour: int = Field(7, ge=0, le=23, description="Час начала (07:00)")
    auto_close_time: str | None = Field("09:00", description="Время автозакрытия")

    # По специальностям
    start_numbers: dict = Field(
        default={"cardiology": 1, "dermatology": 15, "stomatology": 3},
        description="Стартовые номера по специальностям",
    )

    max_per_day: dict = Field(
        default={"cardiology": 15, "dermatology": 20, "stomatology": 12},
        description="Максимум записей в день",
    )


# ===================== СТАТУС ПРОВЕРКИ =====================


class QueueStatusCheck(BaseModel):
    """Проверка статуса очереди"""

    queue_open: bool = Field(..., description="Очередь открыта")
    within_hours: bool = Field(..., description="В рабочих часах")
    has_slots: bool = Field(..., description="Есть свободные места")
    current_time: datetime = Field(..., description="Текущее время")
    queue_start_time: str = Field(..., description="Время начала очереди")
    opened_at: datetime | None = Field(None, description="Время открытия приема")
