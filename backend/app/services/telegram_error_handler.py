"""
Telegram Bot Error Handler

✅ SECURITY: Comprehensive error handling and retry logic for Telegram bot operations
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TelegramErrorHandler:
    """Error handler for Telegram bot operations"""

    # Retryable error codes from Telegram API
    RETRYABLE_ERRORS = {
        429: "Too Many Requests",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout",
    }

    # Non-retryable errors (don't retry)
    NON_RETRYABLE_ERRORS = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
    }

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.error_counts: Dict[str, int] = {}

    async def retry_with_backoff(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> Optional[T]:
        """
        Execute function with exponential backoff retry
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
        
        Returns:
            Function result or None if all retries failed
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                result = await func(*args, **kwargs)
                
                # Reset error count on success
                func_name = getattr(func, "__name__", "unknown")
                if func_name in self.error_counts:
                    del self.error_counts[func_name]
                
                return result

            except Exception as e:
                last_exception = e
                func_name = getattr(func, "__name__", "unknown")
                
                # Check if error is retryable
                error_code = getattr(e, "status_code", None)
                if error_code in self.NON_RETRYABLE_ERRORS:
                    logger.error(
                        f"Non-retryable error in {func_name}: {self.NON_RETRYABLE_ERRORS[error_code]}"
                    )
                    return None

                # Track error count
                self.error_counts[func_name] = self.error_counts.get(func_name, 0) + 1

                if attempt < self.max_retries - 1:
                    # Calculate exponential backoff delay
                    delay = self.base_delay * (2 ** attempt)
                    
                    # Check for rate limiting
                    if error_code == 429:
                        retry_after = getattr(e, "retry_after", delay)
                        delay = max(delay, retry_after)
                        logger.warning(
                            f"Rate limited in {func_name}, waiting {delay}s before retry {attempt + 1}/{self.max_retries}"
                        )
                    else:
                        logger.warning(
                            f"Error in {func_name}, retrying in {delay}s (attempt {attempt + 1}/{self.max_retries}): {e}"
                        )

                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"All retries exhausted for {func_name}: {e}",
                        exc_info=True
                    )

        return None

    def should_retry(self, error: Exception) -> bool:
        """Check if error should be retried"""
        error_code = getattr(error, "status_code", None)
        
        if error_code in self.NON_RETRYABLE_ERRORS:
            return False
        
        if error_code in self.RETRYABLE_ERRORS:
            return True
        
        # Retry on network errors
        error_type = type(error).__name__
        if "Connection" in error_type or "Timeout" in error_type:
            return True
        
        return False

    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        return {
            "error_counts": self.error_counts.copy(),
            "total_errors": sum(self.error_counts.values()),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def reset_stats(self):
        """Reset error statistics"""
        self.error_counts.clear()


# Global error handler instance
telegram_error_handler = TelegramErrorHandler(max_retries=3, base_delay=1.0)


