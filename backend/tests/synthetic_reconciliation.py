"""Install the real 0123 SQLite substrate in metadata-only test fixtures."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations


def install_reconciliation_fence(engine) -> None:
    path = Path(__file__).resolve().parents[1] / "alembic/versions/0123_reconciliation_fence.py"
    spec = importlib.util.spec_from_file_location("synthetic_reconciliation_0123", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Synthetic reconciliation migration unavailable")
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
