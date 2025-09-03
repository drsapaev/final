"""queue tickets

Revision ID: 20250814_0003_queue
Revises: 20250814_0002_auth
Create Date: 2025-08-14 12:03:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20250814_0003"
down_revision = "20250814_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    def has_table(t: str) -> bool:
        return t in insp.get_table_names()

    def has_index(t: str, name: str) -> bool:
        if t not in insp.get_table_names():
            return False
        return any(ix["name"] == name for ix in insp.get_indexes(t))

    def has_uc(t: str, name: str) -> bool:
        # В SQLite get_unique_constraints может быть не реализован — ловим аккуратно
        try:
            return any(uc.get("name") == name for uc in insp.get_unique_constraints(t))
        except Exception:
            return False

    # 1) Таблица
    if not has_table("queue_tickets"):
        op.create_table(
            "queue_tickets",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("department", sa.String(length=64), nullable=False),
            sa.Column("date_str", sa.String(length=16), nullable=False),
            sa.Column("ticket_number", sa.Integer(), nullable=False),
            sa.Column(
                "status",
                sa.String(length=16),
                nullable=False,
                server_default=sa.text("'waiting'"),
            ),
        )

    # 2) Индексы (создаём только если их нет)
    if not has_index("queue_tickets", "ix_queue_dep"):
        op.create_index("ix_queue_dep", "queue_tickets", ["department"])
    if not has_index("queue_tickets", "ix_queue_date"):
        op.create_index("ix_queue_date", "queue_tickets", ["date_str"])
    if not has_index("queue_tickets", "ix_queue_status"):
        op.create_index("ix_queue_status", "queue_tickets", ["status"])
    if not has_index("queue_tickets", "ix_queue_ticket"):
        op.create_index("ix_queue_ticket", "queue_tickets", ["ticket_number"])

    # 3) Уникальность (department, date_str, ticket_number) — диалект-зависимо
    if bind.dialect.name == "sqlite":
        if not has_index("queue_tickets", "uq_queue_dep_date_ticket__uniq_idx"):
            op.create_index(
                "uq_queue_dep_date_ticket__uniq_idx",
                "queue_tickets",
                ["department", "date_str", "ticket_number"],
                unique=True,
            )
    else:
        if not has_uc("queue_tickets", "uq_queue_dep_date_ticket"):
            op.create_unique_constraint(
                "uq_queue_dep_date_ticket",
                "queue_tickets",
                ["department", "date_str", "ticket_number"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    def has_table(t: str) -> bool:
        return t in insp.get_table_names()

    def has_index(t: str, name: str) -> bool:
        if t not in insp.get_table_names():
            return False
        return any(ix["name"] == name for ix in insp.get_indexes(t))

    def has_uc(t: str, name: str) -> bool:
        try:
            return any(uc.get("name") == name for uc in insp.get_unique_constraints(t))
        except Exception:
            return False

    # Удаляем уникальность
    if bind.dialect.name == "sqlite":
        if has_index("queue_tickets", "uq_queue_dep_date_ticket__uniq_idx"):
            op.drop_index(
                "uq_queue_dep_date_ticket__uniq_idx", table_name="queue_tickets"
            )
    else:
        if has_uc("queue_tickets", "uq_queue_dep_date_ticket"):
            op.drop_constraint(
                "uq_queue_dep_date_ticket", "queue_tickets", type_="unique"
            )

    # Индексы
    for ix in ["ix_queue_ticket", "ix_queue_status", "ix_queue_date", "ix_queue_dep"]:
        if has_index("queue_tickets", ix):
            op.drop_index(ix, table_name="queue_tickets")

    # Таблица
    if has_table("queue_tickets"):
        op.drop_table("queue_tickets")
