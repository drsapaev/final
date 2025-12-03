"""
Transaction Management Utilities

✅ SECURITY: Provides explicit transaction boundaries for critical operations
to prevent partial updates, data inconsistency, and race conditions.
"""
import logging
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Generator, TypeVar

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

T = TypeVar("T")


@contextmanager
def transaction(db: Session) -> Generator[Session, None, None]:
    """
    Context manager for explicit transaction boundaries
    
    Usage:
        with transaction(db) as txn:
            # Perform operations
            txn.add(obj)
            # Transaction commits automatically on exit
            # Rolls back on exception
    """
    try:
        yield db
        db.commit()
        logger.debug("Transaction committed successfully")
    except Exception as e:
        db.rollback()
        logger.error(f"Transaction rolled back due to error: {e}")
        raise


def with_transaction(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator for functions that need explicit transaction boundaries
    
    Usage:
        @with_transaction
        def critical_operation(db: Session, ...):
            # Operations are wrapped in a transaction
            db.add(obj)
            # Commits on success, rolls back on exception
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        # Find db session in args or kwargs
        db = None
        for arg in args:
            if isinstance(arg, Session):
                db = arg
                break
        if not db and "db" in kwargs:
            db = kwargs["db"]
        
        if not db:
            # No db session found, execute without transaction wrapper
            logger.warning(f"Function {func.__name__} called without db session, executing without transaction")
            return func(*args, **kwargs)
        
        try:
            result = func(*args, **kwargs)
            db.commit()
            logger.debug(f"Transaction committed for {func.__name__}")
            return result
        except Exception as e:
            db.rollback()
            logger.error(f"Transaction rolled back for {func.__name__} due to error: {e}")
            raise
    
    return wrapper


def retry_on_deadlock(max_retries: int = 3, delay: float = 0.1):
    """
    Decorator to retry operations on database deadlocks
    
    Usage:
        @retry_on_deadlock(max_retries=5, delay=0.2)
        def critical_operation(db: Session, ...):
            # Will retry on deadlock errors
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            import time
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Check if it's a deadlock error
                    error_str = str(e).lower()
                    is_deadlock = (
                        "deadlock" in error_str or
                        "lock" in error_str or
                        "timeout" in error_str
                    )
                    
                    if is_deadlock and attempt < max_retries - 1:
                        logger.warning(
                            f"Deadlock detected in {func.__name__}, attempt {attempt + 1}/{max_retries}, retrying..."
                        )
                        time.sleep(delay * (attempt + 1))  # Exponential backoff
                        last_exception = e
                        continue
                    else:
                        raise
            
            # If we exhausted retries, raise the last exception
            if last_exception:
                raise last_exception
            
            # Should never reach here
            raise RuntimeError("Unexpected retry logic error")
        
        return wrapper
    return decorator


