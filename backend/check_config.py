#!/usr/bin/env python3
from app.core.config import settings

print(f"SECRET_KEY: {settings.SECRET_KEY}")
print(f"ALGORITHM: {getattr(settings, 'ALGORITHM', 'HS256')}")