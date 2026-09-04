"""#2772 live-finding: /password-reset/* shared one 3/hour bucket —
the owner's own recovery journey (initiate + F5-validate + confirm)
locked themselves out. Mapping now splits initiate (email cost) from
token operations (secret = the single-use token itself)."""
from app.middleware.security_middleware import SecurityMiddleware


def _mw():
    mw = object.__new__(SecurityMiddleware)
    mw.rate_limits = {
        "login": {"requests": 5, "window": 300},
        "password_reset": {"requests": 3, "window": 3600},
        "password_reset_token": {"requests": 30, "window": 300},
        "2fa_verify": {"requests": 10, "window": 300},
        "password_change": {"requests": 5, "window": 3600},
        "session": {"requests": 600, "window": 3600},
        "api": {"requests": 5000, "window": 3600},
    }
    return mw


def test_mapping_splits_initiate_from_token_ops():
    mw = _mw()
    assert mw._get_endpoint_type("/api/v1/password-reset/initiate") == "password_reset"
    assert mw._get_endpoint_type("/api/v1/password-reset/validate-token") == "password_reset_token"
    assert mw._get_endpoint_type("/api/v1/password-reset/confirm") == "password_reset_token"


def test_token_ops_bucket_is_typo_friendly():
    mw = _mw()
    assert mw.rate_limits["password_reset_token"]["requests"] >= 30
    assert mw.rate_limits["password_reset_token"]["window"] <= 600
    # initiate остаётся дорогим (письмо = деньги)
    assert mw.rate_limits["password_reset"] == {"requests": 3, "window": 3600}
