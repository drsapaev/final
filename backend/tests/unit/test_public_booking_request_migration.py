"""Migration metadata regressions for public booking requests."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_DIR = Path(__file__).resolve().parents[2]
CONFIRMATION_REVISION = "0086_public_booking_confirm"


def test_confirmation_revision_fits_postgres_alembic_version_column():
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    revision = ScriptDirectory.from_config(config).get_revision(CONFIRMATION_REVISION)

    assert revision is not None
    assert len(revision.revision) <= 32
