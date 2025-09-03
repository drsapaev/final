# app/crud/payment_webhook.py
from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_, MetaData, select, Table
from sqlalchemy.orm import Session

from app.models.payment_webhook import (
    PaymentProvider,
    PaymentTransaction,
    PaymentWebhook,
)
from app.schemas.payment_webhook import (
    PaymentProviderCreate,
    PaymentProviderUpdate,
    PaymentTransactionCreate,
    PaymentTransactionUpdate,
    PaymentWebhookCreate,
    PaymentWebhookUpdate,
)


def _payment_webhooks(db: Session) -> Table:
    md = MetaData()
    return Table("payment_webhooks", md, autoload_with=db.get_bind())


def _payment_transactions(db: Session) -> Table:
    md = MetaData()
    return Table("payment_transactions", md, autoload_with=db.get_bind())


def _payment_providers(db: Session) -> Table:
    md = MetaData()
    return Table("payment_providers", md, autoload_with=db.get_bind())


# === PaymentWebhook CRUD ===


def create_webhook(db: Session, webhook_in: PaymentWebhookCreate) -> PaymentWebhook:
    """Создание вебхука"""
    t = _payment_webhooks(db)

    # Подготавливаем данные с автоматическим временем
    data = webhook_in.model_dump()
    data["created_at"] = datetime.utcnow()

    row = db.execute(t.insert().values(**data).returning(t)).mappings().first()
    db.commit()
    assert row is not None
    return PaymentWebhook(**dict(row))


def get_webhook_by_id(db: Session, webhook_id: int) -> Optional[PaymentWebhook]:
    """Получение вебхука по ID"""
    t = _payment_webhooks(db)
    row = db.execute(select(t).where(t.c.id == webhook_id)).mappings().first()
    return PaymentWebhook(**dict(row)) if row else None


def get_webhook_by_webhook_id(db: Session, webhook_id: str) -> Optional[PaymentWebhook]:
    """Получение вебхука по webhook_id"""
    t = _payment_webhooks(db)
    row = db.execute(select(t).where(t.c.webhook_id == webhook_id)).mappings().first()
    return PaymentWebhook(**dict(row)) if row else None


def get_webhook_by_transaction_id(
    db: Session, transaction_id: str
) -> Optional[PaymentWebhook]:
    """Получение вебхука по transaction_id"""
    t = _payment_webhooks(db)
    row = (
        db.execute(select(t).where(t.c.transaction_id == transaction_id))
        .mappings()
        .first()
    )
    return PaymentWebhook(**dict(row)) if row else None


def get_webhooks_by_provider(
    db: Session, provider: str, skip: int = 0, limit: int = 100
) -> List[PaymentWebhook]:
    """Получение вебхуков по провайдеру"""
    t = _payment_webhooks(db)
    rows = (
        db.execute(select(t).where(t.c.provider == provider).offset(skip).limit(limit))
        .mappings()
        .all()
    )
    return [PaymentWebhook(**dict(row)) for row in rows]


def get_pending_webhooks(
    db: Session, skip: int = 0, limit: int = 100
) -> List[PaymentWebhook]:
    """Получение ожидающих вебхуков"""
    t = _payment_webhooks(db)
    rows = (
        db.execute(select(t).where(t.c.status == "pending").offset(skip).limit(limit))
        .mappings()
        .all()
    )
    return [PaymentWebhook(**dict(row)) for row in rows]


def get_failed_webhooks(
    db: Session, skip: int = 0, limit: int = 100
) -> List[PaymentWebhook]:
    """Получение неудачных вебхуков"""
    t = _payment_webhooks(db)
    rows = (
        db.execute(select(t).where(t.c.status == "failed").offset(skip).limit(limit))
        .mappings()
        .all()
    )
    return [PaymentWebhook(**dict(row)) for row in rows]


def update_webhook(
    db: Session, webhook_id: int, webhook_in: dict
) -> Optional[PaymentWebhook]:
    """Обновление вебхука"""
    t = _payment_webhooks(db)

    # Подготавливаем данные с автоматическим временем
    data = webhook_in.copy()
    data["processed_at"] = datetime.utcnow()

    row = (
        db.execute(t.update().where(t.c.id == webhook_id).values(**data).returning(t))
        .mappings()
        .first()
    )
    if row:
        db.commit()
        return PaymentWebhook(**dict(row))
    return None


def get_all_webhooks(
    db: Session, skip: int = 0, limit: int = 100
) -> List[PaymentWebhook]:
    """Получение всех вебхуков"""
    t = _payment_webhooks(db)
    rows = db.execute(select(t).offset(skip).limit(limit)).mappings().all()
    return [PaymentWebhook(**dict(row)) for row in rows]


def count_webhooks(db: Session) -> int:
    """Подсчёт общего количества вебхуков"""
    t = _payment_webhooks(db)
    result = db.execute(select(t.c.id)).scalars().all()
    return len(result)


# === PaymentTransaction CRUD ===


def create_transaction(
    db: Session, transaction_in: PaymentTransactionCreate
) -> PaymentTransaction:
    """Создание транзакции"""
    t = _payment_transactions(db)

    # Подготавливаем данные с автоматическим временем
    data = transaction_in.model_dump()
    now = datetime.utcnow()
    data["created_at"] = now
    data["updated_at"] = now

    row = db.execute(t.insert().values(**data).returning(t)).mappings().first()
    db.commit()
    assert row is not None
    return PaymentTransaction(**dict(row))


def get_transaction_by_id(
    db: Session, transaction_id: int
) -> Optional[PaymentTransaction]:
    """Получение транзакции по ID"""
    t = _payment_transactions(db)
    row = db.execute(select(t).where(t.c.id == transaction_id)).mappings().first()
    return PaymentTransaction(**dict(row)) if row else None


def get_transaction_by_transaction_id(
    db: Session, transaction_id: str
) -> Optional[PaymentTransaction]:
    """Получение транзакции по transaction_id"""
    t = _payment_transactions(db)
    row = (
        db.execute(select(t).where(t.c.transaction_id == transaction_id))
        .mappings()
        .first()
    )
    return PaymentTransaction(**dict(row)) if row else None


def get_transactions_by_provider(
    db: Session, provider: str, skip: int = 0, limit: int = 100
) -> List[PaymentTransaction]:
    """Получение транзакций по провайдеру"""
    t = _payment_transactions(db)
    rows = (
        db.execute(select(t).where(t.c.provider == provider).offset(skip).limit(limit))
        .mappings()
        .all()
    )
    return [PaymentTransaction(**dict(row)) for row in rows]


def get_transactions_by_status(
    db: Session, status: str, skip: int = 0, limit: int = 100
) -> List[PaymentTransaction]:
    """Получение транзакций по статусу"""
    t = _payment_transactions(db)
    rows = (
        db.execute(select(t).where(t.c.status == status).offset(skip).limit(limit))
        .mappings()
        .all()
    )
    return [PaymentTransaction(**dict(row)) for row in rows]


def get_transactions_by_visit(db: Session, visit_id: int) -> List[PaymentTransaction]:
    """Получение транзакций по ID визита"""
    t = _payment_transactions(db)
    rows = db.execute(select(t).where(t.c.visit_id == visit_id)).mappings().all()
    return [PaymentTransaction(**dict(row)) for row in rows]


def get_successful_transactions_by_visit(
    db: Session, visit_id: int
) -> List[PaymentTransaction]:
    """Получение успешных транзакций по ID визита"""
    t = _payment_transactions(db)
    rows = (
        db.execute(
            select(t).where(and_(t.c.visit_id == visit_id, t.c.status == "success"))
        )
        .mappings()
        .all()
    )
    return [PaymentTransaction(**dict(row)) for row in rows]


def update_transaction(
    db: Session, transaction_id: int, transaction_in: dict
) -> Optional[PaymentTransaction]:
    """Обновление транзакции"""
    t = _payment_transactions(db)

    # Подготавливаем данные с автоматическим временем
    data = transaction_in.copy()
    data["updated_at"] = datetime.utcnow()

    row = (
        db.execute(
            t.update().where(t.c.id == transaction_id).values(**data).returning(t)
        )
        .mappings()
        .first()
    )
    if row:
        db.commit()
        return PaymentTransaction(**dict(row))
    return None


def get_all_transactions(
    db: Session, skip: int = 0, limit: int = 100
) -> List[PaymentTransaction]:
    """Получение всех транзакций"""
    t = _payment_transactions(db)
    rows = db.execute(select(t).offset(skip).limit(limit)).mappings().all()
    return [PaymentTransaction(**dict(row)) for row in rows]


def count_transactions(db: Session) -> int:
    """Подсчёт общего количества транзакций"""
    t = _payment_transactions(db)
    result = db.execute(select(t.c.id)).scalars().all()
    return len(result)


# === PaymentProvider CRUD ===


def create_provider(db: Session, provider_in: PaymentProviderCreate) -> PaymentProvider:
    """Создание провайдера"""
    t = _payment_providers(db)

    # Подготавливаем данные с автоматическим временем
    data = provider_in.model_dump()
    now = datetime.utcnow()
    data["created_at"] = now
    data["updated_at"] = now

    row = db.execute(t.insert().values(**data).returning(t)).mappings().first()
    db.commit()
    assert row is not None
    return PaymentProvider(**dict(row))


def get_provider_by_id(db: Session, provider_id: int) -> Optional[PaymentProvider]:
    """Получение провайдера по ID"""
    t = _payment_providers(db)
    row = db.execute(select(t).where(t.c.id == provider_id)).mappings().first()
    return PaymentProvider(**dict(row)) if row else None


def get_provider_by_code(db: Session, code: str) -> Optional[PaymentProvider]:
    """Получение провайдера по коду"""
    t = _payment_providers(db)
    row = db.execute(select(t).where(t.c.code == code)).mappings().first()
    return PaymentProvider(**dict(row)) if row else None


def get_active_providers(db: Session) -> List[PaymentProvider]:
    """Получение активных провайдеров"""
    t = _payment_providers(db)
    rows = db.execute(select(t).where(t.c.is_active == True)).mappings().all()
    return [PaymentProvider(**dict(row)) for row in rows]


def get_provider_by_provider_type(
    db: Session, provider_type: str
) -> Optional[PaymentProvider]:
    """Получаем провайдера по типу (payme, click, etc.)"""
    return get_provider_by_code(db, provider_type)


def update_provider(
    db: Session, provider_id: int, provider_in: PaymentProviderUpdate
) -> Optional[PaymentProvider]:
    """Обновление провайдера"""
    t = _payment_providers(db)

    # Подготавливаем данные с автоматическим временем
    data = provider_in.model_dump(exclude_unset=True)
    data["updated_at"] = datetime.utcnow()

    row = (
        db.execute(t.update().where(t.c.id == provider_id).values(**data).returning(t))
        .mappings()
        .first()
    )
    if row:
        db.commit()
        return PaymentProvider(**dict(row))
    return None


def delete_provider(db: Session, provider_id: int) -> bool:
    """Удаление провайдера"""
    t = _payment_providers(db)
    result = db.execute(t.delete().where(t.c.id == provider_id))
    db.commit()
    return result.rowcount > 0


def get_all_providers(
    db: Session, skip: int = 0, limit: int = 100
) -> List[PaymentProvider]:
    """Получение всех провайдеров"""
    t = _payment_providers(db)
    rows = db.execute(select(t).offset(skip).limit(limit)).mappings().all()
    return [PaymentProvider(**dict(row)) for row in rows]


# Создаём экземпляры CRUD классов для совместимости с API
class CRUDPaymentWebhook:
    def create(self, db: Session, obj_in: PaymentWebhookCreate) -> PaymentWebhook:
        return create_webhook(db, obj_in)

    def get(self, db: Session, id: int) -> Optional[PaymentWebhook]:
        return get_webhook_by_id(db, id)

    def get_multi(
        self, db: Session, skip: int = 0, limit: int = 100
    ) -> List[PaymentWebhook]:
        return get_all_webhooks(db, skip, limit)

    def update(
        self, db: Session, db_obj: PaymentWebhook, obj_in: dict
    ) -> Optional[PaymentWebhook]:
        return update_webhook(db, db_obj.id, obj_in)

    def count(self, db: Session) -> int:
        return count_webhooks(db)


class CRUDPaymentTransaction:
    def create(
        self, db: Session, obj_in: PaymentTransactionCreate
    ) -> PaymentTransaction:
        return create_transaction(db, obj_in)

    def get(self, db: Session, id: int) -> Optional[PaymentTransaction]:
        return get_transaction_by_id(db, id)

    def get_multi(
        self, db: Session, skip: int = 0, limit: int = 100
    ) -> List[PaymentTransaction]:
        return get_all_transactions(db, skip, limit)

    def update(
        self, db: Session, db_obj: PaymentTransaction, obj_in: dict
    ) -> Optional[PaymentTransaction]:
        return update_transaction(db, db_obj.id, obj_in)

    def count(self, db: Session) -> int:
        return count_transactions(db)


class CRUDPaymentProvider:
    def create(self, db: Session, obj_in: PaymentProviderCreate) -> PaymentProvider:
        return create_provider(db, obj_in)

    def get(self, db: Session, id: int) -> Optional[PaymentProvider]:
        return get_provider_by_id(db, id)

    def get_multi(
        self, db: Session, skip: int = 0, limit: int = 100
    ) -> List[PaymentProvider]:
        return get_all_providers(db, skip, limit)

    def update(
        self, db: Session, db_obj: PaymentProvider, obj_in: dict
    ) -> Optional[PaymentProvider]:
        return update_provider(db, db_obj.id, obj_in)

    def remove(self, db: Session, id: int) -> bool:
        return delete_provider(db, id)


# Создаём экземпляры CRUD классов
payment_webhook = CRUDPaymentWebhook()
payment_transaction = CRUDPaymentTransaction()
payment_provider = CRUDPaymentProvider()
