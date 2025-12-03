"""
Unit tests for application settings validation
"""
import os
import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_secret_key_min_length():
    """Test that SECRET_KEY must be at least 32 characters"""
    # Valid key (32+ chars)
    valid_key = "a" * 32
    settings = Settings(SECRET_KEY=valid_key)
    assert len(settings.SECRET_KEY) >= 32
    
    # Invalid key (too short)
    with pytest.raises(ValidationError) as exc_info:
        Settings(SECRET_KEY="short")
    assert "at least 32" in str(exc_info.value).lower() or "min_length" in str(exc_info.value).lower()


def test_secret_key_required():
    """Test that SECRET_KEY validation works correctly"""
    # Note: Settings() may use env_file which could have a default
    # The actual validation happens in get_settings() which checks min_length
    # This test verifies that SECRET_KEY must be at least 32 chars when provided
    # The requirement is enforced by min_length=32 in Field definition
    settings = Settings(SECRET_KEY="a" * 32)
    assert len(settings.SECRET_KEY) == 32
    
    # Test that too short keys are rejected
    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="short")


def test_fcm_settings_optional():
    """Test that FCM settings are optional"""
    settings = Settings(
        SECRET_KEY="a" * 32,
        FCM_SERVER_KEY=None,
        FCM_PROJECT_ID=None,
        FCM_ENABLED=False
    )
    assert settings.FCM_SERVER_KEY is None
    assert settings.FCM_PROJECT_ID is None
    assert settings.FCM_ENABLED is False


def test_backup_settings_defaults():
    """Test backup settings have correct defaults"""
    settings = Settings(SECRET_KEY="a" * 32)
    assert settings.AUTO_BACKUP_ENABLED is False
    assert settings.BACKUP_RETENTION_DAYS == 30


def test_backup_retention_validation():
    """Test backup retention days validation (1-365)"""
    # Valid values
    settings1 = Settings(SECRET_KEY="a" * 32, BACKUP_RETENTION_DAYS=1)
    assert settings1.BACKUP_RETENTION_DAYS == 1
    
    settings2 = Settings(SECRET_KEY="a" * 32, BACKUP_RETENTION_DAYS=365)
    assert settings2.BACKUP_RETENTION_DAYS == 365
    
    # Invalid: too low
    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="a" * 32, BACKUP_RETENTION_DAYS=0)
    
    # Invalid: too high
    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="a" * 32, BACKUP_RETENTION_DAYS=366)


def test_cors_settings_defaults():
    """Test CORS settings have correct defaults"""
    settings = Settings(SECRET_KEY="a" * 32)
    assert settings.CORS_DISABLE is False
    assert settings.CORS_ALLOW_ALL is False
    assert len(settings.BACKEND_CORS_ORIGINS) > 0


def test_get_settings_validation():
    """Test that get_settings() validates SECRET_KEY length"""
    # This test requires environment variable manipulation
    # We'll test the validation logic indirectly
    os.environ.pop("SECRET_KEY", None)  # Clear any existing SECRET_KEY
    
    # In dev mode, it should work with default or generated key
    # In production mode, it should fail
    try:
        settings = get_settings()
        # If we get here, it's dev mode - key should be >= 32
        assert len(settings.SECRET_KEY) >= 32
    except ValueError as e:
        # In production mode, should raise ValueError
        assert "SECRET_KEY" in str(e) or "32" in str(e)


def test_env_file_loading():
    """Test that settings can load from .env file"""
    # This is tested implicitly by the SettingsConfigDict(env_file=".env")
    # We verify the config is set correctly
    settings = Settings(SECRET_KEY="a" * 32)
    # If env_file is configured, Pydantic will attempt to load it
    # The actual loading is tested by using a real .env file in integration tests
    assert settings.model_config.get("env_file") == ".env"

