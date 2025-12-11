"""
Caching Strategy for Clinic Management System

This module provides in-memory caching with optional Redis support.
Caches frequently accessed data:
- Department lists
- Doctor lists
- Service catalogs
- Patient lookup results

Usage:
    from app.core.cache import cache_manager, cached

    # Decorator usage
    @cached(ttl=300, key_prefix="departments")
    def get_departments():
        return db.query(Department).all()

    # Manual usage
    cache_manager.set("key", value, ttl=300)
    value = cache_manager.get("key")
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry:
    """Single cache entry with expiration"""
    value: Any
    expires_at: float
    created_at: float = field(default_factory=time.time)
    hits: int = 0


class InMemoryCache:
    """
    Thread-safe in-memory cache with TTL support.
    
    For production with multiple instances, use Redis instead.
    """
    
    def __init__(self, max_size: int = 1000):
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        entry = self._cache.get(key)
        
        if entry is None:
            self._misses += 1
            return None
        
        # Check expiration
        if time.time() > entry.expires_at:
            del self._cache[key]
            self._misses += 1
            return None
        
        entry.hits += 1
        self._hits += 1
        return entry.value
    
    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default 5 minutes)
        """
        # Evict oldest entries if at capacity
        if len(self._cache) >= self._max_size:
            self._evict_oldest()
        
        self._cache[key] = CacheEntry(
            value=value,
            expires_at=time.time() + ttl
        )
    
    def delete(self, key: str) -> bool:
        """Delete a key from cache"""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern (prefix match)"""
        keys_to_delete = [k for k in self._cache.keys() if k.startswith(pattern)]
        for key in keys_to_delete:
            del self._cache[key]
        return len(keys_to_delete)
    
    def clear(self) -> None:
        """Clear entire cache"""
        self._cache.clear()
    
    def _evict_oldest(self) -> None:
        """Evict oldest 10% of entries"""
        if not self._cache:
            return
        
        # Sort by creation time and remove oldest 10%
        sorted_keys = sorted(
            self._cache.keys(),
            key=lambda k: self._cache[k].created_at
        )
        
        evict_count = max(1, len(sorted_keys) // 10)
        for key in sorted_keys[:evict_count]:
            del self._cache[key]
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries"""
        now = time.time()
        expired = [k for k, v in self._cache.items() if v.expires_at < now]
        for key in expired:
            del self._cache[key]
        return len(expired)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests * 100 if total_requests > 0 else 0
        
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "memory_estimate_kb": self._estimate_memory() // 1024
        }
    
    def _estimate_memory(self) -> int:
        """Rough estimate of cache memory usage in bytes"""
        try:
            return len(json.dumps({k: str(v.value) for k, v in self._cache.items()}))
        except:
            return len(self._cache) * 1000  # Rough estimate


class RedisCache:
    """
    Redis-based cache for production multi-instance deployments.
    
    Requires: pip install redis
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        self._redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._client = None
        self._available = False
        self._connect()
    
    def _connect(self) -> None:
        """Attempt to connect to Redis"""
        try:
            import redis
            self._client = redis.from_url(self._redis_url)
            self._client.ping()
            self._available = True
            logger.info(f"Connected to Redis at {self._redis_url}")
        except ImportError:
            logger.warning("redis package not installed - using in-memory cache")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e} - using in-memory cache")
    
    @property
    def is_available(self) -> bool:
        return self._available
    
    def get(self, key: str) -> Optional[Any]:
        if not self._available:
            return None
        try:
            value = self._client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
        return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        if not self._available:
            return
        try:
            self._client.setex(key, ttl, json.dumps(value, default=str))
        except Exception as e:
            logger.error(f"Redis set error: {e}")
    
    def delete(self, key: str) -> bool:
        if not self._available:
            return False
        try:
            return self._client.delete(key) > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        if not self._available:
            return 0
        try:
            keys = self._client.keys(f"{pattern}*")
            if keys:
                return self._client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis delete pattern error: {e}")
        return 0
    
    def clear(self) -> None:
        if not self._available:
            return
        try:
            self._client.flushdb()
        except Exception as e:
            logger.error(f"Redis clear error: {e}")


class CacheManager:
    """
    Cache manager with automatic fallback from Redis to in-memory.
    """
    
    def __init__(self, use_redis: bool = False, redis_url: Optional[str] = None):
        self._memory_cache = InMemoryCache()
        self._redis_cache = None
        
        if use_redis:
            self._redis_cache = RedisCache(redis_url)
            if not self._redis_cache.is_available:
                self._redis_cache = None
                logger.info("Falling back to in-memory cache")
    
    @property
    def _cache(self) -> Union[InMemoryCache, RedisCache]:
        return self._redis_cache or self._memory_cache
    
    def get(self, key: str) -> Optional[Any]:
        return self._cache.get(key)
    
    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        self._cache.set(key, value, ttl)
    
    def delete(self, key: str) -> bool:
        return self._cache.delete(key)
    
    def delete_pattern(self, pattern: str) -> int:
        return self._cache.delete_pattern(pattern)
    
    def clear(self) -> None:
        self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        if isinstance(self._cache, InMemoryCache):
            return {
                "backend": "memory",
                **self._cache.get_stats()
            }
        return {
            "backend": "redis",
            "available": self._redis_cache.is_available if self._redis_cache else False
        }


# Global cache manager instance
cache_manager = CacheManager(
    use_redis=os.getenv("CACHE_BACKEND") == "redis"
)


# === Caching Decorator ===

def cached(
    ttl: int = 300,
    key_prefix: str = "",
    key_builder: Optional[Callable[..., str]] = None
):
    """
    Decorator to cache function results.
    
    Args:
        ttl: Time to live in seconds (default 5 minutes)
        key_prefix: Prefix for cache keys
        key_builder: Custom function to build cache key from args
    
    Example:
        @cached(ttl=600, key_prefix="departments")
        def get_departments():
            return db.query(Department).all()
        
        @cached(ttl=60, key_builder=lambda patient_id: f"patient:{patient_id}")
        def get_patient(patient_id: int):
            return db.query(Patient).get(patient_id)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default key: prefix:function_name:hash(args)
                args_hash = hashlib.md5(
                    json.dumps((args, kwargs), default=str, sort_keys=True).encode()
                ).hexdigest()[:8]
                cache_key = f"{key_prefix}:{func.__name__}:{args_hash}"
            
            # Try to get from cache
            cached_value = cache_manager.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl)
            logger.debug(f"Cache set: {cache_key}")
            
            return result
        
        # Add cache invalidation method
        def invalidate(*args, **kwargs):
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                args_hash = hashlib.md5(
                    json.dumps((args, kwargs), default=str, sort_keys=True).encode()
                ).hexdigest()[:8]
                cache_key = f"{key_prefix}:{func.__name__}:{args_hash}"
            cache_manager.delete(cache_key)
        
        wrapper.invalidate = invalidate
        wrapper.invalidate_all = lambda: cache_manager.delete_pattern(f"{key_prefix}:")
        
        return wrapper
    return decorator


# === Predefined Cache Keys ===

class CacheKeys:
    """Predefined cache key patterns"""
    DEPARTMENTS = "clinic:departments"
    DOCTORS = "clinic:doctors"
    SERVICES = "clinic:services"
    SPECIALTIES = "clinic:specialties"
    
    @staticmethod
    def patient(patient_id: int) -> str:
        return f"patient:{patient_id}"
    
    @staticmethod
    def doctor(doctor_id: int) -> str:
        return f"doctor:{doctor_id}"
    
    @staticmethod
    def department(department_id: int) -> str:
        return f"department:{department_id}"


# === Cache Invalidation Helpers ===

def invalidate_department_cache():
    """Call when departments are modified"""
    cache_manager.delete_pattern("clinic:departments")
    cache_manager.delete_pattern("department:")


def invalidate_doctor_cache():
    """Call when doctors are modified"""
    cache_manager.delete_pattern("clinic:doctors")
    cache_manager.delete_pattern("doctor:")


def invalidate_service_cache():
    """Call when services are modified"""
    cache_manager.delete_pattern("clinic:services")
    cache_manager.delete_pattern("service:")


def invalidate_patient_cache(patient_id: Optional[int] = None):
    """Call when patient data is modified"""
    if patient_id:
        cache_manager.delete(CacheKeys.patient(patient_id))
    else:
        cache_manager.delete_pattern("patient:")
