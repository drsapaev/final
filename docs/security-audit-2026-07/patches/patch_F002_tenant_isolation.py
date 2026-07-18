"""
PATCH F-002: Tenant-изоляция таблицы messages (clinic_id)
=========================================================

Файлы:
  1. backend/app/models/message.py      — добавить clinic_id
  2. backend/alembic/versions/XXXX_add_clinic_id_to_messages.py  — миграция
  3. backend/app/core/messaging_config.py  — can_send_message с clinic-проверкой
  4. backend/app/services/messages_api_service.py — validate_recipient с clinic-проверкой
  5. backend/app/crud/message.py — фильтр по clinic_id во всех запросах

ВНИМАНИЕ: требует поля clinic_id в таблице users (или clinic_id через auth context).
Если users.clinic_id не существует — добавить отдельной миграцией.
"""

# === 1. Модель: backend/app/models/message.py ===
MODEL_PATCH = '''
# Добавить поле clinic_id в Message (после recipient_id):

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sender_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    recipient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # НОВОЕ: clinic_id для tenant-изоляции
    clinic_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant isolation: clinic/branch this message belongs to"
    )

    message_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # ... остальные поля без изменений
'''

# === 2. Alembic миграция ===
MIGRATION_PATCH = '''
# backend/alembic/versions/0030_add_clinic_id_to_messages.py
"""add clinic_id to messages for tenant isolation

Revision ID: 0030_add_clinic_id_to_messages
Revises: 0029_telegram_patient_onboarding_requests
Create Date: 2026-07-06

"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    # Шаг 1: добавляем колонку как nullable (чтобы заполнить существующие данные)
    op.add_column(
        "messages",
        sa.Column("clinic_id", sa.Integer(), nullable=True),
    )

    # Шаг 2: заполняем clinic_id из sender's clinic
    op.execute("""
        UPDATE messages m
        SET clinic_id = u.clinic_id
        FROM users u
        WHERE m.sender_id = u.id
          AND u.clinic_id IS NOT NULL
    """)

    # Шаг 3: для оставшихся NULL — ставим clinic_id = 1 (default clinic)
    # ВАЖНО: замените на реальный ID дефолтной клиники в вашей системе
    op.execute("""
        UPDATE messages SET clinic_id = 1 WHERE clinic_id IS NULL
    """)

    # Шаг 4: делаем колонку NOT NULL
    op.alter_column("messages", "clinic_id", nullable=False)

    # Шаг 5: добавляем FK + индекс
    op.create_foreign_key(
        "fk_messages_clinic_id",
        "messages",
        "clinics",
        ["clinic_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_messages_clinic_id",
        "messages",
        ["clinic_id"],
    )


def downgrade():
    op.drop_index("ix_messages_clinic_id", table_name="messages")
    op.drop_constraint("fk_messages_clinic_id", "messages", type_="foreignkey")
    op.drop_column("messages", "clinic_id")
'''

# === 3. messaging_config.py — clinic-aware проверка ===
CONFIG_PATCH = '''
# backend/app/core/messaging_config.py

from app.models.user import User


def can_send_message(sender: User, recipient: User) -> bool:
    """
    Проверить, может ли отправитель писать получателю.

    Учитывает:
    1. Role-based permissions (как раньше)
    2. Tenant isolation: оба пользователя в одной клинике
    """
    allowed_recipients = MESSAGING_PERMISSIONS.get(sender.role, [])
    if recipient.role not in allowed_recipients:
        return False

    # Tenant isolation: оба пользователя должны быть в одной клинике
    sender_clinic = getattr(sender, "clinic_id", None)
    recipient_clinic = getattr(recipient, "clinic_id", None)

    # Если clinic_id не настроен у пользователя — fallback к разрешению
    # (для single-clinic развёртываний, где clinic_id может быть NULL)
    if sender_clinic is not None and recipient_clinic is not None:
        if sender_clinic != recipient_clinic:
            return False

    return True


# Обратная совместимость: старая сигнатура (для existing callers)
def can_send_message_by_role(sender_role: str, recipient_role: str) -> bool:
    """Legacy: только role-based проверка, без tenant."""
    allowed = MESSAGING_PERMISSIONS.get(sender_role, [])
    return recipient_role in allowed
'''

# === 4. messages_api_service.py — validate_recipient ===
SERVICE_PATCH = '''
# backend/app/services/messages_api_service.py (строки 120-135)

def validate_recipient(self, *, recipient_id: int, current_user: User) -> User:
    if recipient_id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя отправить сообщение самому себе")

    recipient = self.repository.get_user(recipient_id)
    if not recipient:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # ИЗМЕНЕНО: передаём User-объекты вместо role-строк
    if not can_send_message(current_user, recipient):
        raise HTTPException(
            status_code=403,
            detail="Нет прав для отправки сообщения этому пользователю",
        )
    return recipient
'''

# === 5. crud/message.py — clinic_id в каждом запросе ===
CRUD_PATCH = '''
# backend/app/crud/message.py

class CRUDMessage:
    def create(self, db, *, sender_id, obj_in, clinic_id: int) -> Message:
        """Создать новое сообщение с привязкой к clinic_id."""
        db_obj = Message(
            sender_id=sender_id,
            recipient_id=obj_in.recipient_id,
            content=obj_in.content,
            patient_id=getattr(obj_in, "patient_id", None),
            clinic_id=clinic_id,  # НОВОЕ
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_conversation(
        self, db, *, user1_id, user2_id, skip=0, limit=50, clinic_id: int | None = None
    ) -> tuple[list[Message], int]:
        """Получить переписку — с фильтром по clinic_id."""
        query = db.query(Message).filter(
            or_(
                and_(Message.sender_id == user1_id, Message.recipient_id == user2_id),
                and_(Message.sender_id == user2_id, Message.recipient_id == user1_id)
            ),
            or_(
                and_(Message.sender_id == user1_id, Message.is_deleted_by_sender == False),
                and_(Message.recipient_id == user1_id, Message.is_deleted_by_recipient == False)
            )
        )
        # НОВОЕ: фильтр по clinic_id
        if clinic_id is not None:
            query = query.filter(Message.clinic_id == clinic_id)

        query = query.order_by(desc(Message.created_at))
        total = query.count()
        messages = query.offset(skip).limit(limit).all()
        return messages, total

    def get_conversations_list(
        self, db, *, user_id, clinic_id: int | None = None
    ) -> list[dict]:
        """Список бесед — с фильтром по clinic_id."""
        query = db.query(Message).filter(
            or_(Message.sender_id == user_id, Message.recipient_id == user_id)
        )
        if clinic_id is not None:
            query = query.filter(Message.clinic_id == clinic_id)
        # ... остальное без изменений
'''

if __name__ == "__main__":
    print("F-002 PATCH — Tenant isolation via clinic_id")
    print("=" * 60)
    for name, content in [
        ("MODEL_PATCH", MODEL_PATCH),
        ("MIGRATION_PATCH", MIGRATION_PATCH),
        ("CONFIG_PATCH", CONFIG_PATCH),
        ("SERVICE_PATCH", SERVICE_PATCH),
        ("CRUD_PATCH", CRUD_PATCH),
    ]:
        print(f"\n--- {name} ---")
        print(content[:400] + "...")
