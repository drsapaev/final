"""
AI Rate Limiter - Контроль частоты AI запросов.

Защищает от:
1. DDoS на AI endpoints
2. Превышение лимитов провайдеров (OpenAI: 10k RPM)
3. Исчерпание бюджета
"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class AIRateLimiter:
    """
    Rate limiter для AI endpoints.
    
    Два уровня лимитов:
    1. Per-user: X запросов в час (защита от злоупотреблений)
    2. Per-provider: Y запросов в минуту (защита от лимитов API)
    """
    
    def __init__(
        self,
        user_limit_per_hour: int = 60,
        provider_limit_per_minute: int = 100
    ):
        self.user_limit_per_hour = user_limit_per_hour
        self.provider_limit_per_minute = provider_limit_per_minute
        
        # Storage: {user_id: [timestamps]}
        self._user_requests: Dict[int, List[datetime]] = defaultdict(list)
        
        # Storage: {provider_name: [timestamps]}
        self._provider_requests: Dict[str, List[datetime]] = defaultdict(list)
        
        # Async lock for thread safety
        self._lock = asyncio.Lock()
        
        # Cleanup interval
        self._last_cleanup = datetime.utcnow()
        self._cleanup_interval = timedelta(minutes=5)
    
    async def check_user_limit(self, user_id: int) -> Tuple[bool, Optional[int]]:
        """
        Проверка лимита пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            (allowed, retry_after_seconds)
            - (True, None) если запрос разрешен
            - (False, X) если нужно подождать X секунд
        """
        async with self._lock:
            await self._maybe_cleanup()
            
            now = datetime.utcnow()
            cutoff = now - timedelta(hours=1)
            
            # Очистка старых записей для этого пользователя
            self._user_requests[user_id] = [
                ts for ts in self._user_requests[user_id] if ts > cutoff
            ]
            
            current_count = len(self._user_requests[user_id])
            
            if current_count >= self.user_limit_per_hour:
                # Вычисляем когда освободится слот
                oldest = min(self._user_requests[user_id])
                retry_after = int((oldest + timedelta(hours=1) - now).total_seconds()) + 1
                
                logger.warning(
                    f"Rate limit exceeded for user {user_id}: "
                    f"{current_count}/{self.user_limit_per_hour} requests/hour"
                )
                
                return False, max(1, retry_after)
            
            # Записываем запрос
            self._user_requests[user_id].append(now)
            return True, None
    
    async def check_provider_limit(self, provider: str) -> Tuple[bool, Optional[int]]:
        """
        Проверка лимита провайдера.
        
        Args:
            provider: Имя провайдера (openai, gemini, deepseek)
            
        Returns:
            (allowed, retry_after_seconds)
        """
        async with self._lock:
            now = datetime.utcnow()
            cutoff = now - timedelta(minutes=1)
            
            # Очистка старых записей
            self._provider_requests[provider] = [
                ts for ts in self._provider_requests[provider] if ts > cutoff
            ]
            
            current_count = len(self._provider_requests[provider])
            
            if current_count >= self.provider_limit_per_minute:
                oldest = min(self._provider_requests[provider])
                retry_after = int((oldest + timedelta(minutes=1) - now).total_seconds()) + 1
                
                logger.warning(
                    f"Provider rate limit reached for {provider}: "
                    f"{current_count}/{self.provider_limit_per_minute} requests/minute"
                )
                
                return False, max(1, retry_after)
            
            self._provider_requests[provider].append(now)
            return True, None
    
    async def _maybe_cleanup(self):
        """Периодическая очистка старых записей"""
        now = datetime.utcnow()
        
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        self._last_cleanup = now
        
        # Очистка user requests старше 1 часа
        user_cutoff = now - timedelta(hours=1)
        empty_users = []
        
        for user_id, timestamps in self._user_requests.items():
            self._user_requests[user_id] = [ts for ts in timestamps if ts > user_cutoff]
            if not self._user_requests[user_id]:
                empty_users.append(user_id)
        
        for user_id in empty_users:
            del self._user_requests[user_id]
        
        # Очистка provider requests старше 1 минуты
        provider_cutoff = now - timedelta(minutes=1)
        empty_providers = []
        
        for provider, timestamps in self._provider_requests.items():
            self._provider_requests[provider] = [ts for ts in timestamps if ts > provider_cutoff]
            if not self._provider_requests[provider]:
                empty_providers.append(provider)
        
        for provider in empty_providers:
            del self._provider_requests[provider]
        
        logger.debug(
            f"Rate limiter cleanup: {len(self._user_requests)} users, "
            f"{len(self._provider_requests)} providers tracked"
        )
    
    def get_user_usage(self, user_id: int) -> Dict[str, int]:
        """Получить статистику использования пользователем"""
        count = len(self._user_requests.get(user_id, []))
        return {
            "requests_used": count,
            "requests_limit": self.user_limit_per_hour,
            "remaining": max(0, self.user_limit_per_hour - count),
            "reset_in_seconds": 3600,  # Приблизительно
        }
    
    def get_provider_usage(self, provider: str) -> Dict[str, int]:
        """Получить статистику использования провайдера"""
        count = len(self._provider_requests.get(provider, []))
        return {
            "requests_used": count,
            "requests_limit": self.provider_limit_per_minute,
            "remaining": max(0, self.provider_limit_per_minute - count),
            "reset_in_seconds": 60,
        }


# Singleton instance
_rate_limiter: Optional[AIRateLimiter] = None


def get_rate_limiter() -> AIRateLimiter:
    """Get singleton rate limiter instance"""
    global _rate_limiter
    
    if _rate_limiter is None:
        from app.core.config import settings
        _rate_limiter = AIRateLimiter(
            user_limit_per_hour=settings.AI_RATE_LIMIT_PER_USER_HOUR,
            provider_limit_per_minute=settings.AI_RATE_LIMIT_PER_PROVIDER_MINUTE
        )
    
    return _rate_limiter


async def enforce_rate_limit(user_id: int):
    """
    FastAPI dependency для проверки rate limit.
    
    Raises HTTPException 429 если лимит превышен.
    
    Usage:
        @router.post("/ai/suggest")
        async def suggest(
            user_id: int = Depends(get_user_id_from_token),
            _: None = Depends(enforce_rate_limit)
        ):
            ...
    """
    limiter = get_rate_limiter()
    allowed, retry_after = await limiter.check_user_limit(user_id)
    
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "AI rate limit exceeded",
                "retry_after_seconds": retry_after,
                "limit": limiter.user_limit_per_hour,
                "period": "1 hour"
            },
            headers={"Retry-After": str(retry_after)}
        )
