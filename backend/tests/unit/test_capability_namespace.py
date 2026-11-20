"""The v1 namespace is stable and does not conflate schema identifiers."""
import importlib.util
from pathlib import Path

import pytest

from app.db.capability_namespace import capability_schema_name


def test_known_v1_vector():
    assert capability_schema_name("public") == "clinic_internal_5fb2309029087ddd402703a4392c9faa"


def test_exact_utf8_identifiers_have_distinct_names():
    names = ["public", "Public", "Клиника", 'a"b', "x" * 63, "я" * 31]
    results = [capability_schema_name(name) for name in names]
    assert len(set(results)) == len(names)
    assert all(len(result.encode("ascii")) < 63 for result in results)


@pytest.mark.parametrize("name", ["public", "Клиника", 'a"b', "space \\quote'", "x" * 63])
def test_0120_frozen_migration_naming_matches_runtime(name):
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0120_all_free_decision_capability.py"
    spec = importlib.util.spec_from_file_location("namespace_migration_0120", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._private_name(name) == capability_schema_name(name)


@pytest.mark.parametrize("name", ["", "a\0b", "x" * 64, "я" * 32, "\ud800", None, 123])
def test_invalid_postgres_identifiers_are_rejected(name):
    with pytest.raises(ValueError):
        capability_schema_name(name)
