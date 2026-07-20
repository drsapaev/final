"""
FA-011: Secrets Manager — encrypted file approach for API keys.

Instead of storing API keys in plaintext .env, this module:
1. Reads a master key from a separate file (MASTER_KEY_FILE env var)
2. Decrypts API keys from an encrypted secrets file (SECRETS_FILE env var)
3. Caches decrypted keys in memory (never logged)

For production with HashiCorp Vault / AWS KMS, replace the implementation
of _load_from_encrypted_file() with vault client calls.

Master key file permissions: chmod 600, owned by app user only.
Secrets file format (JSON, encrypted with master key):
{
  "OPENAI_API_KEY": {"ciphertext": "gAAAAA...", "key_id": "master"},
  "DEEPSEEK_API_KEY": {"ciphertext": "gAAAAA...", "key_id": "master"},
  ...
}

To generate master key:
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

To encrypt a secret:
  python -c "
  from cryptography.fernet import Fernet
  import json
  key = open('master.key').read().strip()
  f = Fernet(key)
  secret = 'your-api-key-here'
  print(json.dumps({'ciphertext': f.encrypt(secret.encode()).decode(), 'key_id': 'master'}))
  "
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class SecretsManager:
    """FA-011: Encrypted secrets manager with graceful fallback to env vars."""

    def __init__(self):
        self._cache: dict[str, str] = {}
        self._master_key: bytes | None = None
        self._secrets_file: Path | None = None
        self._initialized = False

    def _initialize(self):
        """Lazily load master key + secrets file path."""
        if self._initialized:
            return
        self._initialized = True

        master_key_path = os.getenv("MASTER_KEY_FILE")
        secrets_file_path = os.getenv("SECRETS_FILE")

        if master_key_path and secrets_file_path:
            try:
                key_path = Path(master_key_path)
                if not key_path.exists():
                    logger.warning(f"FA-011: Master key file not found: {master_key_path}")
                    return

                # Check file permissions (must be 600 or 400)
                stat = key_path.stat()
                if stat.st_mode & 0o077:
                    logger.warning(
                        f"FA-011: Master key file has insecure permissions "
                        f"(mode {oct(stat.st_mode & 0o777)}), expected 600 or 400"
                    )

                self._master_key = key_path.read_bytes().strip()
                self._secrets_file = Path(secrets_file_path)
                logger.info(f"FA-011: Secrets manager initialized (file: {secrets_file_path})")
            except Exception as e:
                logger.error(f"FA-011: Failed to initialize secrets manager: {e}")
                self._master_key = None
                self._secrets_file = None

    def get_secret(self, name: str, default: str | None = None) -> str | None:
        """Get a secret by name. Falls back to environment variable if not in encrypted store."""
        # Check cache first
        if name in self._cache:
            return self._cache[name]

        self._initialize()

        # Try encrypted file first
        if self._master_key and self._secrets_file:
            try:
                value = self._load_from_encrypted_file(name)
                if value is not None:
                    self._cache[name] = value
                    return value
            except Exception as e:
                logger.warning(f"FA-011: Failed to decrypt secret {name}: {e}")

        # Fallback to environment variable
        env_value = os.getenv(name)
        if env_value:
            self._cache[name] = env_value
            return env_value

        return default

    def _load_from_encrypted_file(self, name: str) -> str | None:
        """Decrypt a secret from the encrypted secrets file."""
        if not self._secrets_file or not self._secrets_file.exists():
            return None

        from cryptography.fernet import Fernet

        cipher = Fernet(self._master_key)
        secrets_data = json.loads(self._secrets_file.read_text())

        if name not in secrets_data:
            return None

        entry = secrets_data[name]
        ciphertext = entry["ciphertext"]
        return cipher.decrypt(ciphertext.encode()).decode()

    def reload(self):
        """Clear cache and reinitialize (for key rotation)."""
        self._cache.clear()
        self._master_key = None
        self._secrets_file = None
        self._initialized = False


# Singleton
_secrets_manager = SecretsManager()


def get_secret(name: str, default: str | None = None) -> str | None:
    """FA-011: Get a secret from encrypted store or environment."""
    return _secrets_manager.get_secret(name, default)
