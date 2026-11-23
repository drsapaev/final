from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.visit import Visit


class PaymentVisit(Base):
    """
    Связь между платежом и визитами.
    Позволяет одному платежу покрывать несколько визитов.
    """

    __tablename__ = "payment_visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("visits.id", ondelete="CASCADE"), nullable=False, index=True
    )  # ✅ FIX: Junction table requires both FKs to be NOT NULL for referential integrity
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
        comment="Часть общей суммы платежа за этот конкретный визит",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )

    # Relationships
    payment: Mapped[Payment] = relationship(
        "Payment", back_populates="payment_visits"
    )
    visit: Mapped[Visit] = relationship("Visit", foreign_keys=[visit_id])


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("visits.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )  # ✅ SECURITY: RESTRICT to prevent visit deletion if payment exists (financial integrity)

    # Финансовая информация
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="UZS")

    # Способ и статус платежа
    method: Mapped[str] = mapped_column(
        String(32), nullable=False, default="cash"
    )  # cash|card|transfer|online|click|payme|kaspi
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="paid"
    )  # pending|processing|paid|failed|cancelled|refunded|void

    # Данные чека/квитанции
    receipt_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Идемпотентность кассовых платежей (issue 3859, CSH-FE-008 remainder):
    # клиентский ключ запроса. Не имеет UNIQUE-констрейнта, потому что
    # grouped-аллокация создаёт НЕСКОЛЬКО строк платежа под одним ключом;
    # дедупликационным якорем служит таблица payment_client_requests.
    client_request_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment=(
            "Ключ идемпотентности клиента (UUID): все строки одной "
            "групповой аллокации несут один и тот же ключ"
        ),
    )

    # Онлайн-платежи
    provider: Mapped[str | None] = mapped_column(
        String(32), nullable=True, index=True
    )  # click|payme|kaspi
    provider_payment_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )  # ID у провайдера
    provider_transaction_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )  # ID транзакции
    payment_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )  # URL для оплаты

    # Дополнительные данные от провайдера
    provider_data: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Данные от провайдера
    commission: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True, default=0
    )  # Комиссия

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=lambda: datetime.now(UTC)
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Возврат средств
    refunded_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True, default=None,
        comment="Сумма возврата (может быть частичной)"
    )
    refund_reason: Mapped[str | None] = mapped_column(
        String(512), nullable=True,
        comment="Причина возврата"
    )
    refunded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Дата и время возврата"
    )
    refunded_by: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="ID кассира, выполнившего возврат"
    )

    # Relationships
    payment_visits: Mapped[list[PaymentVisit]] = relationship(
        "PaymentVisit",
        back_populates="payment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Связи (временно отключены для отладки)
    # webhooks: Mapped[list["PaymentWebhook"]] = relationship(
    #     "PaymentWebhook",
    #     back_populates="payment",
    #     cascade="all, delete-orphan"
    # )


class PaymentClientRequest(Base):
    """Дедупликационный якорь кассовых платежей (issue 3859).

    Одна строка на клиентский ``client_request_id`` (UUID, генерируется
    фронтендом один раз на жизненный цикл модального окна оплаты).
    УНИКАЛЬНЫЙ индекс — это серверный гарантий того, что повторный запрос
    с тем же ключом (потеря ответа в сети, повторное нажатие) не создаст
    второй платёж: повтор получает сохранённый снимок ответа исходной
    операции (``response_payload``), а не новую строку в ``payments``.

    Почему отдельная таблица, а не UNIQUE-колонка ``payments``:
    grouped-аллокация создаёт N строк платежа под одним ключом, что
    не выразить уникальностью на ``payments``; кроме того, снимок ответа
    (включая allocations) невосстановим из строк платежа после того,
    как долг визита изменился последующими платежами.
    """

    __tablename__ = "payment_client_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_request_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="Клиентский ключ идемпотентности — UNIQUE: один якорь на intent",
    )
    endpoint: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="single | grouped — эндпоинт, создавший якорь",
    )
    response_payload: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="Снимок ответа исходной операции для реплея (JSON)",
    )
    request_fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment=(
            "RETRO-FIN-001: SHA-256 канонического fingerprint intent'а "
            "(эндпоинт + пациент/визиты + сумма + метод). Реплей ключа с "
            "другим intent отклоняется 409 вместо ложного успеха; NULL у "
            "исторических якорей — реплей без проверки intent"
        ),
    )
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Кассир, создавший платёж (ID пользователя)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
