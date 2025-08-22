from datetime import datetime, timedelta
from jose import jwt
from app.core.config import settings

def create_access_token(subject: str | int, expires_minutes: int = 60) -> str:
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    payload = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.AUTH_SECRET, algorithm=settings.AUTH_ALGORITHM)
