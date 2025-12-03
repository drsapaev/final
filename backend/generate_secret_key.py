#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate secure SECRET_KEY for production

Usage:
    python generate_secret_key.py
"""
import secrets

def generate_secret_key():
    """Generate a secure random secret key"""
    key = secrets.token_urlsafe(32)
    print("=" * 80)
    print("GENERATED SECRET_KEY")
    print("=" * 80)
    print()
    print(f"SECRET_KEY={key}")
    print()
    print("=" * 80)
    print("INSTRUCTIONS:")
    print("=" * 80)
    print("1. Copy the SECRET_KEY above")
    print("2. Add it to your .env file:")
    print(f"   SECRET_KEY={key}")
    print("3. NEVER commit .env to version control!")
    print("4. Keep this key secure and never share it!")
    print("=" * 80)
    return key

if __name__ == "__main__":
    generate_secret_key()


