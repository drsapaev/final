"""
Standardized API response helpers.

Usage:
    from app.api.utils.responses import not_found, forbidden, success_response
    
    # Raise not found error
    if not patient:
        not_found("Пациент не найден")
    
    # Return success response
    return success_response(data={"id": 1}, message="Created successfully")
"""

from typing import Any, Dict, Optional

from fastapi import HTTPException, status


# ===================== ERROR RESPONSES =====================

def not_found(message: str = "Ресурс не найден") -> None:
    """
    Raise HTTP 404 Not Found error.
    
    Args:
        message: Error message
    
    Raises:
        HTTPException: 404 Not Found
    """
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=message
    )


def forbidden(message: str = "Доступ запрещён") -> None:
    """
    Raise HTTP 403 Forbidden error.
    
    Args:
        message: Error message
    
    Raises:
        HTTPException: 403 Forbidden
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=message
    )


def unauthorized(message: str = "Требуется авторизация") -> None:
    """
    Raise HTTP 401 Unauthorized error.
    
    Args:
        message: Error message
    
    Raises:
        HTTPException: 401 Unauthorized
    """
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"}
    )


def bad_request(message: str) -> None:
    """
    Raise HTTP 400 Bad Request error.
    
    Args:
        message: Error message
    
    Raises:
        HTTPException: 400 Bad Request
    """
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=message
    )


def conflict(message: str = "Конфликт данных") -> None:
    """
    Raise HTTP 409 Conflict error.
    
    Args:
        message: Error message
    
    Raises:
        HTTPException: 409 Conflict
    """
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=message
    )


def rate_limited(
    message: str = "Слишком много запросов", 
    retry_after: Optional[int] = None
) -> None:
    """
    Raise HTTP 429 Too Many Requests error.
    
    Args:
        message: Error message
        retry_after: Seconds until retry is allowed
    
    Raises:
        HTTPException: 429 Too Many Requests
    """
    headers = {"Retry-After": str(retry_after)} if retry_after else None
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=message,
        headers=headers
    )


def server_error(message: str = "Внутренняя ошибка сервера") -> None:
    """
    Raise HTTP 500 Internal Server Error.
    
    Args:
        message: Error message
    
    Raises:
        HTTPException: 500 Internal Server Error
    """
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=message
    )


# ===================== SUCCESS RESPONSES =====================

def success_response(
    data: Any = None,
    message: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create standardized success response.
    
    Args:
        data: Response data
        message: Optional success message
        meta: Optional metadata (pagination, etc.)
    
    Returns:
        Standardized response dict
    
    Example:
        >>> success_response(data={"id": 1}, message="Created")
        {"status": "success", "message": "Created", "data": {"id": 1}}
    """
    response: Dict[str, Any] = {"status": "success"}
    
    if message:
        response["message"] = message
    
    if data is not None:
        response["data"] = data
    
    if meta:
        response["meta"] = meta
    
    return response


def paginated_response(
    items: list,
    total: int,
    page: int = 1,
    size: int = 20
) -> Dict[str, Any]:
    """
    Create standardized paginated response.
    
    Args:
        items: List of items
        total: Total number of items
        page: Current page number
        size: Items per page
    
    Returns:
        Paginated response dict
    
    Example:
        >>> paginated_response(items=[...], total=100, page=1, size=20)
        {
            "items": [...],
            "total": 100,
            "page": 1,
            "size": 20,
            "pages": 5,
            "has_next": True,
            "has_prev": False
        }
    """
    pages = (total + size - 1) // size if size > 0 else 0
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
        "has_next": page < pages,
        "has_prev": page > 1
    }


def created_response(data: Any, message: str = "Успешно создано") -> Dict[str, Any]:
    """Create response for resource creation."""
    return success_response(data=data, message=message)


def updated_response(data: Any, message: str = "Успешно обновлено") -> Dict[str, Any]:
    """Create response for resource update."""
    return success_response(data=data, message=message)


def deleted_response(message: str = "Успешно удалено") -> Dict[str, Any]:
    """Create response for resource deletion."""
    return success_response(message=message)
