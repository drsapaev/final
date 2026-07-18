#!/usr/bin/env python3
"""
FA-011: Setup script for encrypted secrets.

Usage:
  # 1. Generate master key
  python -m app.scripts.setup_secrets generate-key

  # 2. Encrypt a secret
  python -m app.scripts.setup_secrets encrypt OPENAI_API_KEY "sk-..."

  # 3. List encrypted secrets
  python -m app.scripts.setup_secrets list

Environment variables:
  MASTER_KEY_FILE — path to master key file (default: /etc/clinic/master.key)
  SECRETS_FILE — path to encrypted secrets JSON (default: /etc/clinic/secrets.json)
"""
import json
import os
import sys
from pathlib import Path


def get_paths():
    master_key_path = os.getenv("MASTER_KEY_FILE", "/etc/clinic/master.key")
    secrets_path = os.getenv("SECRETS_FILE", "/etc/clinic/secrets.json")
    return Path(master_key_path), Path(secrets_path)


def generate_key():
    """Generate a new Fernet master key."""
    from cryptography.fernet import Fernet

    master_key_path, _ = get_paths()
    key = Fernet.generate_key()

    master_key_path.parent.mkdir(parents=True, exist_ok=True)
    master_key_path.write_bytes(key)
    # Set restrictive permissions (600)
    os.chmod(master_key_path, 0o600)

    print(f"Master key generated: {master_key_path}")
    print(f"Permissions: 600 (owner read/write only)")
    print(f"\nAdd to .env:")
    print(f"  MASTER_KEY_FILE={master_key_path}")


def encrypt_secret(name: str, value: str):
    """Encrypt a secret and add it to the secrets file."""
    from cryptography.fernet import Fernet

    master_key_path, secrets_path = get_paths()

    if not master_key_path.exists():
        print(f"ERROR: Master key not found at {master_key_path}")
        print("Run: python -m app.scripts.setup_secrets generate-key")
        sys.exit(1)

    key = master_key_path.read_bytes().strip()
    cipher = Fernet(key)
    ciphertext = cipher.encrypt(value.encode()).decode()

    # Load existing secrets
    secrets = {}
    if secrets_path.exists():
        secrets = json.loads(secrets_path.read_text())

    secrets[name] = {"ciphertext": ciphertext, "key_id": "master"}

    secrets_path.parent.mkdir(parents=True, exist_ok=True)
    secrets_path.write_text(json.dumps(secrets, indent=2))
    os.chmod(secrets_path, 0o600)

    print(f"Secret '{name}' encrypted and saved to {secrets_path}")


def list_secrets():
    """List encrypted secret names."""
    _, secrets_path = get_paths()

    if not secrets_path.exists():
        print("No secrets file found")
        return

    secrets = json.loads(secrets_path.read_text())
    print(f"Secrets file: {secrets_path}")
    print(f"Encrypted secrets ({len(secrets)}):")
    for name in sorted(secrets.keys()):
        print(f"  - {name}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "generate-key":
        generate_key()
    elif cmd == "encrypt":
        if len(sys.argv) < 4:
            print("Usage: encrypt <name> <value>")
            sys.exit(1)
        encrypt_secret(sys.argv[2], sys.argv[3])
    elif cmd == "list":
        list_secrets()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
