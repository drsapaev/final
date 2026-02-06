"""
AI Gateway - Единая точка входа для всех AI операций.

Обеспечивает:
1. Унифицированный контракт ответов (AIResponse)
2. Кэширование с TTL
3. PII анонимизация
4. Rate limiting
5. Circuit breaker для fallback
6. Аудит всех запросов
"""

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, AsyncIterator, Dict, List, Optional

from .ai_interfaces import (
    AIProviderType,
    AIResponse,
    AITaskType,
    IAIGateway,
)
from .pii_anonymizer import get_anonymizer
from .rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit breaker для провайдеров.
    
    States:
    - CLOSED: нормальная работа
    - OPEN: провайдер недоступен, пропускаем его
    - HALF_OPEN: пробуем восстановить
    """
    
    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures: Dict[str, int] = {}
        self._last_failure: Dict[str, datetime] = {}
        self._state: Dict[str, str] = {}  # CLOSED, OPEN, HALF_OPEN
    
    def is_available(self, provider: str) -> bool:
        """Проверка доступности провайдера"""
        state = self._state.get(provider, "CLOSED")
        
        if state == "CLOSED":
            return True
        
        if state == "OPEN":
            # Проверяем таймаут
            last = self._last_failure.get(provider)
            if last and datetime.utcnow() - last > timedelta(seconds=self.recovery_timeout):
                self._state[provider] = "HALF_OPEN"
                logger.info(f"Circuit breaker for {provider}: OPEN -> HALF_OPEN")
                return True
            return False
        
        # HALF_OPEN
        return True
    
    def record_success(self, provider: str):
        """Успешный запрос"""
        if self._state.get(provider) == "HALF_OPEN":
            self._state[provider] = "CLOSED"
            self._failures[provider] = 0
            logger.info(f"Circuit breaker for {provider}: HALF_OPEN -> CLOSED")
    
    def record_failure(self, provider: str):
        """Неудачный запрос"""
        self._failures[provider] = self._failures.get(provider, 0) + 1
        self._last_failure[provider] = datetime.utcnow()
        
        if self._failures[provider] >= self.failure_threshold:
            self._state[provider] = "OPEN"
            logger.warning(
                f"Circuit breaker for {provider}: CLOSED -> OPEN "
                f"(after {self._failures[provider]} failures)"
            )
    
    def reset(self, provider: str):
        """Ручной сброс"""
        self._failures[provider] = 0
        self._state[provider] = "CLOSED"
        logger.info(f"Circuit breaker for {provider}: manually reset to CLOSED")


class AIGateway(IAIGateway):
    """
    Единый AI Gateway - SSOT для всех AI операций.
    
    Все AI запросы проходят через этот шлюз, обеспечивая:
    - Единообразие ответов
    - Безопасность (PII, RBAC)
    - Аудит
    - Надежность (caching, fallback)
    """
    
    def __init__(self):
        from app.core.config import settings
        
        self._cache: Dict[str, tuple] = {}  # hash -> (response, expires_at)
        self._cache_enabled = settings.AI_CACHE_ENABLED
        self._cache_ttl = timedelta(hours=settings.AI_CACHE_TTL_HOURS)
        
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60
        )
        
        self._anonymizer = get_anonymizer()
        self._rate_limiter = get_rate_limiter()
        
        # Provider priority (cost optimization)
        self._provider_priority = [
            AIProviderType.DEEPSEEK,  # Cheapest
            AIProviderType.GEMINI,
            AIProviderType.OPENAI,
            AIProviderType.MOCK,      # Fallback
        ]
        
        logger.info("AI Gateway initialized")
    
    async def execute(
        self,
        task_type: AITaskType,
        payload: Dict[str, Any],
        user_id: int,
        specialty: Optional[str] = None
    ) -> AIResponse:
        """
        Единая точка входа для AI операций.
        
        Pipeline:
        1. Rate limiting check
        2. Cache lookup
        3. PII anonymization
        4. Provider selection (with circuit breaker)
        5. Execute request
        6. Audit logging
        7. Cache result
        8. Return response
        """
        request_id = str(uuid.uuid4())[:8]
        start_time = datetime.utcnow()
        
        logger.info(
            f"[{request_id}] AI Gateway: {task_type.value} "
            f"(user={user_id}, specialty={specialty})"
        )
        
        try:
            # 1. Rate limiting
            allowed, retry_after = await self._rate_limiter.check_user_limit(user_id)
            if not allowed:
                return AIResponse(
                    status="error",
                    data={},
                    provider="none",
                    model="none",
                    latency_ms=0,
                    error=f"Rate limit exceeded. Retry after {retry_after} seconds.",
                    request_id=request_id
                )
            
            # 2. Cache lookup
            cache_key = self._make_cache_key(task_type, payload, specialty)
            cached = self._get_from_cache(cache_key)
            if cached:
                logger.info(f"[{request_id}] Cache hit")
                cached.cached = True
                cached.request_id = request_id
                return cached
            
            # 3. PII anonymization
            clean_payload = self._anonymizer.anonymize(payload)
            removed_fields = self._anonymizer.get_removed_fields()
            
            # 4-5. Execute with fallback
            response = await self._execute_with_fallback(
                task_type, clean_payload, specialty, request_id
            )
            
            # Calculate latency
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            response.latency_ms = latency_ms
            response.request_id = request_id
            
            # Add warnings about anonymized data
            if removed_fields:
                response.warnings.append(
                    f"PII fields were anonymized: {', '.join(removed_fields[:3])}"
                    + ("..." if len(removed_fields) > 3 else "")
                )
            
            # 6. Audit logging
            await self._audit_request(
                user_id=user_id,
                task_type=task_type,
                provider=response.provider,
                success=response.status == "success",
                latency_ms=latency_ms,
                tokens_used=response.tokens_used,
                cached=response.cached
            )
            
            # 7. Cache successful responses
            if response.status == "success" and self._cache_enabled:
                self._save_to_cache(cache_key, response)
            
            return response
            
        except Exception as e:
            logger.exception(f"[{request_id}] AI Gateway error: {e}")
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return AIResponse(
                status="error",
                data={},
                provider="none",
                model="none",
                latency_ms=latency_ms,
                error=str(e),
                request_id=request_id
            )
    
    async def execute_stream(
        self,
        task_type: AITaskType,
        payload: Dict[str, Any],
        user_id: int,
        specialty: Optional[str] = None
    ) -> AsyncIterator[str]:
        """
        Streaming version for chat.
        
        Note: Streaming bypasses cache.
        """
        # Rate limiting
        allowed, _ = await self._rate_limiter.check_user_limit(user_id)
        if not allowed:
            yield "[ERROR] Rate limit exceeded"
            return
        
        # PII anonymization
        clean_payload = self._anonymizer.anonymize(payload)
        
        # Get provider
        provider = await self._get_available_provider()
        if not provider:
            yield "[ERROR] No AI providers available"
            return
        
        # Stream from provider
        try:
            # TODO: Implement actual streaming when providers support it
            # For now, generate full response and yield in chunks
            response = await self.execute(task_type, payload, user_id, specialty)
            
            if response.status == "error":
                yield f"[ERROR] {response.error}"
                return
            
            # Yield content in chunks (simulate streaming)
            content = response.data.get("content", str(response.data))
            chunk_size = 50
            
            for i in range(0, len(content), chunk_size):
                yield content[i:i + chunk_size]
                await asyncio.sleep(0.05)  # Simulate streaming delay
                
        except Exception as e:
            logger.exception(f"Streaming error: {e}")
            yield f"[ERROR] {str(e)}"
    
    async def _execute_with_fallback(
        self,
        task_type: AITaskType,
        payload: Dict[str, Any],
        specialty: Optional[str],
        request_id: str
    ) -> AIResponse:
        """Execute with provider fallback chain"""
        errors = []
        
        for provider_type in self._provider_priority:
            # Check circuit breaker
            if not self._circuit_breaker.is_available(provider_type.value):
                logger.debug(f"[{request_id}] Skipping {provider_type.value} (circuit open)")
                continue
            
            # Check rate limit for provider
            allowed, _ = await self._rate_limiter.check_provider_limit(provider_type.value)
            if not allowed:
                logger.debug(f"[{request_id}] Skipping {provider_type.value} (rate limited)")
                continue
            
            try:
                # Get actual provider instance
                provider = self._get_provider_instance(provider_type)
                if not provider:
                    continue
                
                # Route to appropriate method
                result = await self._route_task(provider, provider_type, task_type, payload, specialty)
                
                # Success!
                self._circuit_breaker.record_success(provider_type.value)
                
                return AIResponse(
                    status="success",
                    data=result if isinstance(result, dict) else {"content": result},
                    provider=provider_type.value,
                    model=getattr(provider, "model", None) or "unknown",
                    latency_ms=0,  # Will be set by caller
                    tokens_used=result.get("tokens_used") if isinstance(result, dict) else None
                )
                
            except Exception as e:
                error_msg = f"{provider_type.value}: {str(e)}"
                errors.append(error_msg)
                logger.warning(f"[{request_id}] Provider {provider_type.value} failed: {e}")
                self._circuit_breaker.record_failure(provider_type.value)
                continue
        
        # All providers failed
        return AIResponse(
            status="error",
            data={},
            provider="none",
            model="none",
            latency_ms=0,
            error=f"All providers failed: {'; '.join(errors)}"
        )
    
    def _get_provider_instance(self, provider_type: AIProviderType):
        """Get provider instance from ai_manager"""
        try:
            from .ai_manager import get_ai_manager
            manager = get_ai_manager()
            return manager.get_provider(provider_type)
        except Exception as e:
            logger.debug(f"Failed to get provider {provider_type}: {e}")
            return None
    
    async def _route_task(
        self,
        provider,
        provider_type: AIProviderType,
        task_type: AITaskType,
        payload: Dict[str, Any],
        specialty: Optional[str]
    ) -> Dict[str, Any]:
        """Route task to appropriate provider method"""
        
        # Task type to method mapping
        if task_type == AITaskType.COMPLAINT_ANALYSIS:
            result = await provider.analyze_complaint(
                payload.get("complaint", ""),
                payload.get("patient_info")
            )
        elif task_type == AITaskType.ICD10_SUGGESTION:
            result = await provider.suggest_icd10(
                payload.get("symptoms", []),
                payload.get("diagnosis")
            )
        elif task_type == AITaskType.LAB_INTERPRETATION:
            result = await provider.interpret_lab_results(
                payload.get("results", []),
                payload.get("patient_info")
            )
        elif task_type == AITaskType.SKIN_ANALYSIS:
            result = await provider.analyze_skin(
                payload.get("image_data"),
                payload.get("metadata")
            )
        elif task_type == AITaskType.ECG_INTERPRETATION:
            result = await provider.interpret_ecg(
                payload.get("ecg_data"),
                payload.get("patient_info")
            )
        elif task_type == AITaskType.DIFFERENTIAL_DIAGNOSIS:
            result = await provider.differential_diagnosis(
                payload.get("symptoms", []),
                payload.get("patient_info")
            )
        elif task_type == AITaskType.CHAT_MESSAGE:
            # Chat message with history support
            from .base_provider import AIRequest
            
            message = payload.get("message", "")
            history = payload.get("history", [])
            specialty_context = payload.get("specialty", specialty)
            
            # Build system prompt based on specialty
            system_prompts = {
                "dentistry": "Вы - AI ассистент для стоматолога. Помогайте с диагностикой зубных заболеваний, планированием лечения и рекомендациями по уходу за полостью рта.",
                "dermatology": "Вы - AI ассистент для дерматолога. Помогайте с анализом кожных заболеваний, дерматоскопией и косметологическими процедурами.",
                "cardiology": "Вы - AI ассистент для кардиолога. Помогайте с интерпретацией ЭКГ, ЭхоКГ, анализом сердечно-сосудистых заболеваний и планированием лечения.",
                "laboratory": "Вы - AI ассистент для лаборатории. Помогайте с интерпретацией результатов анализов, выявлением отклонений и рекомендациями по дополнительным исследованиям.",
                "general": "Вы - медицинский AI ассистент общей практики. Помогайте врачам с диагностикой, дифференциальной диагностикой и планированием обследований.",
            }
            system_prompt = system_prompts.get(specialty_context, "Вы - медицинский AI ассистент. Помогайте врачам с профессиональными вопросами.")
            
            # Build full prompt with history
            full_prompt = ""
            if history:
                full_prompt += "История диалога:\n"
                for msg in history:
                    role = "Врач" if msg.get("role") == "user" else "AI"
                    full_prompt += f"{role}: {msg.get('content', '')}\n"
                full_prompt += "\n"
            
            full_prompt += f"Врач: {message}\nAI:"
            
            request = AIRequest(
                prompt=full_prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=1500
            )
            
            result = await provider.generate(request)
        else:
            # Default: generic generation
            from .base_provider import AIRequest
            request = AIRequest(prompt=json.dumps(payload))
            result = await provider.generate(request)
        
        # Normalize result to dict
        if isinstance(result, str):
            return {"content": result}
        elif hasattr(result, "content"):
            return {"content": result.content, "tokens_used": getattr(result, "tokens_used", None)}
        elif isinstance(result, dict):
            return result
        else:
            return {"content": str(result)}
    
    def _make_cache_key(
        self,
        task_type: AITaskType,
        payload: Dict[str, Any],
        specialty: Optional[str]
    ) -> str:
        """Create cache key from request parameters"""
        key_data = {
            "task": task_type.value,
            "payload": payload,
            "specialty": specialty
        }
        return hashlib.sha256(
            json.dumps(key_data, sort_keys=True, default=str).encode()
        ).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[AIResponse]:
        """Get response from cache if valid"""
        if not self._cache_enabled:
            return None
        
        if cache_key not in self._cache:
            return None
        
        response, expires_at = self._cache[cache_key]
        
        if datetime.utcnow() > expires_at:
            del self._cache[cache_key]
            return None
        
        # Return a copy to avoid mutations
        return response.model_copy()
    
    def _save_to_cache(self, cache_key: str, response: AIResponse):
        """Save response to cache"""
        expires_at = datetime.utcnow() + self._cache_ttl
        self._cache[cache_key] = (response.model_copy(), expires_at)
    
    def clear_cache(self):
        """Clear all cached responses"""
        self._cache.clear()
        logger.info("AI Gateway cache cleared")
    
    async def _audit_request(
        self,
        user_id: int,
        task_type: AITaskType,
        provider: str,
        success: bool,
        latency_ms: int,
        tokens_used: Optional[int],
        cached: bool
    ):
        """Save request to audit log"""
        try:
            from app.db.session import SessionLocal
            from app.models.ai_config import AIUsageLog, AIProvider as AIProviderModel
            
            db = SessionLocal()
            try:
                # Find provider ID
                provider_record = db.query(AIProviderModel).filter(
                    AIProviderModel.name == provider
                ).first()
                
                if not provider_record and provider != "none":
                    logger.warning(f"Provider '{provider}' not found in DB for audit")
                    return
                
                # Create log entry
                log = AIUsageLog(
                    user_id=user_id,
                    provider_id=provider_record.id if provider_record else None,
                    provider_name=provider,
                    task_type=task_type.value,
                    tokens_used=tokens_used,
                    response_time_ms=latency_ms,
                    success=success,
                    cached_response=cached
                )
                
                db.add(log)
                db.commit()
                
            finally:
                db.close()
                
        except Exception as e:
            # Don't fail the request if audit fails
            logger.error(f"Failed to audit AI request: {e}")
    
    def get_available_providers(self) -> List[AIProviderType]:
        """Get list of available (configured) providers"""
        available = []
        for provider_type in self._provider_priority:
            if self._circuit_breaker.is_available(provider_type.value):
                provider = self._get_provider_instance(provider_type)
                if provider:
                    available.append(provider_type)
        return available
    
    async def _get_available_provider(self) -> Optional[Any]:
        """Get first available provider"""
        for provider_type in self._provider_priority:
            if self._circuit_breaker.is_available(provider_type.value):
                provider = self._get_provider_instance(provider_type)
                if provider:
                    return provider
        return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of all providers"""
        health = {
            "status": "healthy",
            "providers": {},
            "cache": {
                "enabled": self._cache_enabled,
                "size": len(self._cache)
            }
        }
        
        for provider_type in self._provider_priority:
            provider_name = provider_type.value
            provider = self._get_provider_instance(provider_type)
            
            health["providers"][provider_name] = {
                "available": provider is not None,
                "circuit_breaker": self._circuit_breaker._state.get(provider_name, "CLOSED"),
                "failures": self._circuit_breaker._failures.get(provider_name, 0)
            }
        
        # Overall status
        available_count = sum(
            1 for p in health["providers"].values() if p["available"]
        )
        if available_count == 0:
            health["status"] = "unhealthy"
        elif available_count < len(self._provider_priority) - 1:  # Exclude MOCK
            health["status"] = "degraded"
        
        return health
    
    def reset_circuit_breaker(self, provider: str):
        """Manually reset circuit breaker for a provider"""
        self._circuit_breaker.reset(provider)


# Singleton
_ai_gateway: Optional[AIGateway] = None


def get_ai_gateway() -> AIGateway:
    """Get singleton AI Gateway instance"""
    global _ai_gateway
    if _ai_gateway is None:
        _ai_gateway = AIGateway()
    return _ai_gateway
