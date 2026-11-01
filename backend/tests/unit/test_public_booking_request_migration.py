"""Migration metadata regressions for public booking requests."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_DIR = Path(__file__).resolve().parents[2]
CONFIRMATION_REVISION = "0086_public_booking_confirm"
BOOKING_OUTBOX_REVISION = "0087_booking_notification_outbox"
REFUND_CLAIM_REVISION = "0088_fm_refund_claim"
MERGE_REVISION = "0089_merge_booking_refund_heads"


def test_confirmation_revision_fits_postgres_alembic_version_column():
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    revision = ScriptDirectory.from_config(config).get_revision(CONFIRMATION_REVISION)

    assert revision is not None
    assert len(revision.revision) <= 32


def test_booking_and_refund_migration_branches_converge_to_one_head():
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    assert len(script.get_heads()) == 1

    merge_revision = script.get_revision(MERGE_REVISION)
    assert merge_revision is not None
    assert set(merge_revision.down_revision) == {
        BOOKING_OUTBOX_REVISION,
        REFUND_CLAIM_REVISION,
    }
    assert len(merge_revision.revision) <= 32
