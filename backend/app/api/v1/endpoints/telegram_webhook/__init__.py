"""
Telegram webhook package.

Re-exports router for backward compatibility with api.py:
    from app.api.v1.endpoints.telegram_webhook import router
"""
from app.api.v1.endpoints.telegram_webhook._routes import router

__all__ = ["router"]
