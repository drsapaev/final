import sys
import os
sys.path.append(os.getcwd())

from app.core.config import settings
from app.services.authentication_service import AuthenticationService

print(f"SECRET_KEY: {settings.SECRET_KEY[:5]}...{settings.SECRET_KEY[-5:]}")
print(f"ALGORITHM: {settings.ALGORITHM}")
print(f"ACCESS_TOKEN_EXPIRE_MINUTES: {settings.ACCESS_TOKEN_EXPIRE_MINUTES}")

auth_service = AuthenticationService()
token = auth_service.create_access_token({"sub": "123", "username": "testuser"})
print(f"Generated Token: {token}")

decoded = auth_service.verify_token(token)
print(f"Decoded: {decoded}")
