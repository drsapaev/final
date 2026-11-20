"""Database safety boundary for isolated PostgreSQL test schemas."""
import pytest
from sqlalchemy.engine import make_url

from tests.integration.test_profile_contact_security_pg import _safe_test_database


@pytest.mark.parametrize(("url", "ci", "allowed"), [
    ("postgresql://synthetic:synthetic@127.0.0.1/clinic_test_temp", False, True),
    ("postgresql://synthetic:synthetic@localhost/clinicdb", True, True),
    ("postgresql://synthetic:synthetic@[::1]/clinicdb", True, True),
    ("postgresql://synthetic:synthetic@localhost/clinicdb", False, False),
    ("postgresql://synthetic:synthetic@remote.example/clinicdb", True, False),
    ("postgresql://synthetic:synthetic@remote.example/clinic_test_temp", False, False),
    ("postgresql://synthetic:synthetic@localhost/clinic_prod", True, False),
    ("sqlite:///clinic_test_temp", True, False),
])
def test_fixture_accepts_only_disposable_local_database(url, ci, allowed):
    assert _safe_test_database(make_url(url), ci=ci) is allowed
