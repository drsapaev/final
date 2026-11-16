"""Persist sensitive 2FA replay/lockout and session revocation state.

Existing 2FA records deliberately retain NULL: no previous sensitive TOTP
step can be inferred safely. The service updates the value while holding the
account's 2FA row lock, in the same transaction as the protected operation.
The separate failure counter cannot be cleared by ordinary 2FA login.
Existing unexpired all-user blacklist markers and inactive users initialize
the corresponding epoch to 1; markers remain intact for safe rollback.
Downgrade requires a coordinated authentication shutdown and must never
silently truncate session tokens.
"""

import sqlalchemy as sa

from alembic import op

revision = "0097_two_factor_sensitive_totp"
down_revision = "0096_passkey_owner_user"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "auth_epoch", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
    )
    # SQLite stores datetime values as text, whose lexical precision can differ
    # from CURRENT_TIMESTAMP. Both forms below compare UTC instants strictly.
    active_expiry = (
        "julianday(token_blacklist.expires_at) > julianday('now')"
        if op.get_bind().dialect.name == "sqlite"
        else "token_blacklist.expires_at > CURRENT_TIMESTAMP"
    )
    op.execute(
        sa.text(
            "UPDATE users SET auth_epoch = 1 WHERE auth_epoch = 0 AND (users.is_active IS NOT TRUE OR EXISTS ("
            "SELECT 1 FROM token_blacklist WHERE token_blacklist.user_id = users.id "
            "AND token_blacklist.reason LIKE 'all_user_tokens:%' AND "
            + active_expiry
            + "))"
        )
    )
    with op.batch_alter_table("user_sessions") as batch_op:
        batch_op.alter_column(
            "refresh_token",
            existing_type=sa.String(128),
            type_=sa.String(512),
            existing_nullable=True,
        )
    with op.batch_alter_table("refresh_tokens") as batch_op:
        batch_op.alter_column(
            "token",
            existing_type=sa.String(255),
            type_=sa.String(512),
            existing_nullable=False,
        )
    with op.batch_alter_table("two_factor_auth") as batch_op:
        batch_op.add_column(
            sa.Column("last_sensitive_totp_step", sa.BigInteger(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "sensitive_failed_attempts",
                sa.Integer(),
                server_default=sa.text("0"),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "sensitive_locked_until", sa.DateTime(timezone=True), nullable=True
            )
        )


def downgrade() -> None:
    nonzero_epoch_exists = (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM users WHERE auth_epoch <> 0 LIMIT 1"))
        .first()
    )
    long_token_exists = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM user_sessions WHERE length(refresh_token) > 128 LIMIT 1"
            )
        )
        .first()
    )
    long_refresh_exists = (
        op.get_bind()
        .execute(
            sa.text("SELECT 1 FROM refresh_tokens WHERE length(token) > 255 LIMIT 1")
        )
        .first()
    )
    if nonzero_epoch_exists:
        raise RuntimeError(
            "Cannot downgrade with nonzero user auth epochs; coordinate credential invalidation and key rotation first"
        )
    if long_token_exists:
        raise RuntimeError(
            "Cannot downgrade while a user session refresh token exceeds 128 characters"
        )
    if long_refresh_exists:
        raise RuntimeError(
            "Cannot downgrade while a stored refresh token exceeds 255 characters"
        )
    with op.batch_alter_table("two_factor_auth") as batch_op:
        batch_op.drop_column("sensitive_locked_until")
        batch_op.drop_column("sensitive_failed_attempts")
        batch_op.drop_column("last_sensitive_totp_step")
    with op.batch_alter_table("user_sessions") as batch_op:
        batch_op.alter_column(
            "refresh_token",
            existing_type=sa.String(512),
            type_=sa.String(128),
            existing_nullable=True,
        )
    with op.batch_alter_table("refresh_tokens") as batch_op:
        batch_op.alter_column(
            "token",
            existing_type=sa.String(512),
            type_=sa.String(255),
            existing_nullable=False,
        )
    op.drop_column("users", "auth_epoch")
