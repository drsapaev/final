"""The development issuer refuses unsafe environments and targets."""
import pytest

from app.scripts.mint_dev_token import mint_dev_token
from app.scripts.reset_dev_db import DevDatabaseSafetyError


@pytest.mark.parametrize("url,env,app_env", [
    ("postgresql://x:y@127.0.0.1/clinic_dev", "production", ""),
    ("postgresql://x:y@127.0.0.1/clinic_dev", "dev", "production"),
    ("postgresql://x:y@remote.example/clinic_dev", "dev", ""),
    ("postgresql://x:y@127.0.0.1/clinic_prod", "dev", ""),
    ("sqlite:///tmp/dev.db", "dev", ""),
    ("postgresql://x:y@127.0.0.1/clinic_dev", "staging", ""),
])
def test_rejects_unsafe_configuration(monkeypatch, url, env, app_env, capsys):
    monkeypatch.setenv("CONFIRM_MINT_DEV_TOKEN", "1")
    monkeypatch.setenv("MINT_DEV_TOKEN_SUBJECT", "SYNTHETIC_user")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENV", env)
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    with pytest.raises((DevDatabaseSafetyError, SystemExit)):
        mint_dev_token()
    assert not capsys.readouterr().out
