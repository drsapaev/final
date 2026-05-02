from __future__ import annotations

import warnings

from app.core.security import get_password_hash, verify_password


def test_password_hashing_does_not_emit_argon2_version_deprecation():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        hashed = get_password_hash("secret123")
        assert verify_password("secret123", hashed) is True
        assert verify_password("wrong", hashed) is False

    assert not any("argon2.__version__" in str(w.message) for w in caught)
