"""Bind new passkeys to the user who enrolled them.

Existing credentials deliberately retain a NULL owner: their true enrollment
owner cannot be established from a patient's current, mutable user link.
Authentication must reject those credentials until they are re-enrolled.
Users also receive a nullable opaque WebAuthn user handle; values are created
on enrollment rather than derived from patient IDs or application secrets.
"""

import sqlalchemy as sa

from alembic import op

revision = "0096_passkey_owner_user"
down_revision = "0095_two_factor_attempt_lockout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("passkey_user_handle", sa.String(43), nullable=True)
    )
    op.create_index(
        "ix_users_passkey_user_handle", "users", ["passkey_user_handle"], unique=True
    )
    with op.batch_alter_table("passkey_credentials") as batch_op:
        batch_op.add_column(
            sa.Column(
                "owner_user_id",
                sa.Integer(),
                nullable=True,
                comment="User who enrolled this credential; NULL means unknown owner",
            ),
        )
        batch_op.create_foreign_key(
            "fk_passkey_credentials_owner_user_id_users",
            "users",
            ["owner_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_passkey_credentials_owner_user_id", ["owner_user_id"])


def downgrade() -> None:
    with op.batch_alter_table("passkey_credentials") as batch_op:
        batch_op.drop_index("ix_passkey_credentials_owner_user_id")
        batch_op.drop_constraint(
            "fk_passkey_credentials_owner_user_id_users", type_="foreignkey"
        )
        batch_op.drop_column("owner_user_id")
    op.drop_index("ix_users_passkey_user_handle", table_name="users")
    op.drop_column("users", "passkey_user_handle")
