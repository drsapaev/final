"""create printing tables and seed staging-safe printers

Revision ID: 0021_printing_tables
Revises: 0020_notification_platform
Create Date: 2026-04-02 00:00:00.000000
"""

from __future__ import annotations

from pathlib import Path

from alembic import op
import sqlalchemy as sa


revision = "0021_printing_tables"
down_revision = "0020_notification_platform"
branch_labels = None
depends_on = None

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "app" / "templates" / "print"


def _template_text(filename: str) -> str:
    template_path = TEMPLATE_DIR / filename
    if not template_path.exists():
        raise FileNotFoundError(f"Print template file not found: {template_path}")
    return template_path.read_text(encoding="utf-8")


def upgrade() -> None:
    op.create_table(
        "printer_configs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=150), nullable=False),
        sa.Column("printer_type", sa.String(length=50), nullable=False),
        sa.Column(
            "connection_type",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'network'"),
        ),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("device_path", sa.String(length=200), nullable=True),
        sa.Column("paper_width", sa.Integer(), nullable=True),
        sa.Column("paper_height", sa.Integer(), nullable=True),
        sa.Column("margins", sa.JSON(), nullable=True),
        sa.Column(
            "encoding",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'utf-8'"),
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("name", name="uq_printer_configs_name"),
    )
    op.create_index(op.f("ix_printer_configs_id"), "printer_configs", ["id"], unique=False)

    op.create_table(
        "print_templates",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "printer_id",
            sa.Integer(),
            sa.ForeignKey("printer_configs.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=150), nullable=False),
        sa.Column("template_type", sa.String(length=50), nullable=False),
        sa.Column("template_content", sa.Text(), nullable=False),
        sa.Column(
            "language",
            sa.String(length=5),
            nullable=False,
            server_default=sa.text("'ru'"),
        ),
        sa.Column(
            "font_size",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("12"),
        ),
        sa.Column(
            "line_spacing",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("char_per_line", sa.Integer(), nullable=True),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(op.f("ix_print_templates_id"), "print_templates", ["id"], unique=False)

    op.create_table(
        "print_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "printer_id",
            sa.Integer(),
            sa.ForeignKey("printer_configs.id"),
            nullable=False,
        ),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("print_templates.id"),
            nullable=True,
        ),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("document_id", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("print_data", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_print_jobs_id"), "print_jobs", ["id"], unique=False)
    op.create_index(op.f("ix_print_jobs_created_at"), "print_jobs", ["created_at"], unique=False)

    # Staging-safe seed data: mock printers make live smoke succeed without hardware.
    op.bulk_insert(
        sa.table(
            "printer_configs",
            sa.column("id", sa.Integer),
            sa.column("name", sa.String),
            sa.column("display_name", sa.String),
            sa.column("printer_type", sa.String),
            sa.column("connection_type", sa.String),
            sa.column("ip_address", sa.String),
            sa.column("port", sa.Integer),
            sa.column("device_path", sa.String),
            sa.column("paper_width", sa.Integer),
            sa.column("paper_height", sa.Integer),
            sa.column("margins", sa.JSON),
            sa.column("encoding", sa.String),
            sa.column("active", sa.Boolean),
            sa.column("is_default", sa.Boolean),
        ),
        [
            {
                "id": 1,
                "name": "ticket_printer",
                "display_name": "Термопринтер кассы",
                "printer_type": "ESC/POS",
                "connection_type": "mock",
                "ip_address": None,
                "port": None,
                "device_path": None,
                "paper_width": 58,
                "paper_height": None,
                "margins": None,
                "encoding": "utf-8",
                "active": True,
                "is_default": True,
            },
            {
                "id": 2,
                "name": "lab_printer",
                "display_name": "A4 принтер лаборатории",
                "printer_type": "A4",
                "connection_type": "mock",
                "ip_address": None,
                "port": None,
                "device_path": None,
                "paper_width": 210,
                "paper_height": 297,
                "margins": None,
                "encoding": "utf-8",
                "active": True,
                "is_default": False,
            },
            {
                "id": 3,
                "name": "prescription_printer",
                "display_name": "A5 принтер рецептов",
                "printer_type": "A5",
                "connection_type": "mock",
                "ip_address": None,
                "port": None,
                "device_path": None,
                "paper_width": 148,
                "paper_height": 210,
                "margins": None,
                "encoding": "utf-8",
                "active": True,
                "is_default": False,
            },
        ],
    )

    op.bulk_insert(
        sa.table(
            "print_templates",
            sa.column("id", sa.Integer),
            sa.column("printer_id", sa.Integer),
            sa.column("name", sa.String),
            sa.column("display_name", sa.String),
            sa.column("template_type", sa.String),
            sa.column("template_content", sa.Text),
            sa.column("language", sa.String),
            sa.column("font_size", sa.Integer),
            sa.column("line_spacing", sa.Integer),
            sa.column("char_per_line", sa.Integer),
            sa.column("active", sa.Boolean),
        ),
        [
            {
                "id": 1,
                "printer_id": 1,
                "name": "ticket_template",
                "display_name": "Шаблон талона",
                "template_type": "ticket",
                "template_content": _template_text("ticket_escpos.j2"),
                "language": "ru",
                "font_size": 12,
                "line_spacing": 1,
                "char_per_line": 42,
                "active": True,
            },
            {
                "id": 2,
                "printer_id": 1,
                "name": "receipt_template",
                "display_name": "Шаблон чека",
                "template_type": "receipt",
                "template_content": _template_text("payment_receipt_escpos.j2"),
                "language": "ru",
                "font_size": 12,
                "line_spacing": 1,
                "char_per_line": 42,
                "active": True,
            },
            {
                "id": 3,
                "printer_id": 2,
                "name": "lab_results_template",
                "display_name": "Шаблон результатов анализов",
                "template_type": "lab_results",
                "template_content": _template_text("lab_results_a4.j2"),
                "language": "ru",
                "font_size": 12,
                "line_spacing": 1,
                "char_per_line": None,
                "active": True,
            },
            {
                "id": 4,
                "printer_id": 3,
                "name": "prescription_template",
                "display_name": "Шаблон рецепта",
                "template_type": "prescription",
                "template_content": _template_text("prescription_a5.j2"),
                "language": "ru",
                "font_size": 12,
                "line_spacing": 1,
                "char_per_line": None,
                "active": True,
            },
            {
                "id": 5,
                "printer_id": 2,
                "name": "medical_certificate_template",
                "display_name": "Шаблон справки",
                "template_type": "medical_certificate",
                "template_content": _template_text("medical_certificate_a4.j2"),
                "language": "ru",
                "font_size": 12,
                "line_spacing": 1,
                "char_per_line": None,
                "active": True,
            },
        ],
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table_name in ("printer_configs", "print_templates", "print_jobs"):
            op.execute(
                sa.text(
                    f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table_name}', 'id'),
                        COALESCE((SELECT MAX(id) FROM {table_name}), 1),
                        EXISTS(SELECT 1 FROM {table_name})
                    )
                    """
                )
            )


def downgrade() -> None:
    op.drop_index(op.f("ix_print_jobs_created_at"), table_name="print_jobs")
    op.drop_index(op.f("ix_print_jobs_id"), table_name="print_jobs")
    op.drop_table("print_jobs")
    op.drop_index(op.f("ix_print_templates_id"), table_name="print_templates")
    op.drop_table("print_templates")
    op.drop_index(op.f("ix_printer_configs_id"), table_name="printer_configs")
    op.drop_table("printer_configs")
