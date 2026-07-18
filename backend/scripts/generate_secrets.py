#!/usr/bin/env python3
"""Secret rotation helper — generates new keys for rotation."""
import secrets
from cryptography.fernet import Fernet

print("=== Secret Rotation Helper ===\n")

print("1. SECRET_KEY (JWT signing):")
print(f"   {secrets.token_urlsafe(48)}")
print()

print("2. ENCRYPTION_KEY (Fernet — bot tokens, API keys):")
print(f"   {Fernet.generate_key().decode()}")
print()

print("3. CSRF Token:")
print(f"   {secrets.token_urlsafe(32)}")
print()

print("4. Webhook Secret:")
print(f"   {secrets.token_urlsafe(32)}")
print()

print("Copy the values to your .env.production file.")
print("See docs/DATA_RETENTION_POLICY.md for rotation procedures.")
