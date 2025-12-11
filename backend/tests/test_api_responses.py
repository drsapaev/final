"""
Tests for API response utilities.

Run: pytest tests/test_api_responses.py -v
"""

import pytest
from fastapi import HTTPException

from app.api.utils.responses import (
    not_found,
    forbidden,
    unauthorized,
    bad_request,
    conflict,
    rate_limited,
    server_error,
    success_response,
    paginated_response,
    created_response,
    updated_response,
    deleted_response,
)


class TestErrorResponses:
    """Tests for error response helpers."""
    
    def test_not_found_raises_404(self):
        """not_found raises HTTPException with 404"""
        with pytest.raises(HTTPException) as exc_info:
            not_found("Patient not found")
        
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Patient not found"
    
    def test_not_found_default_message(self):
        """not_found has default message"""
        with pytest.raises(HTTPException) as exc_info:
            not_found()
        
        assert exc_info.value.status_code == 404
        assert "не найден" in exc_info.value.detail.lower() or "not found" in exc_info.value.detail.lower()
    
    def test_forbidden_raises_403(self):
        """forbidden raises HTTPException with 403"""
        with pytest.raises(HTTPException) as exc_info:
            forbidden("Access denied")
        
        assert exc_info.value.status_code == 403
    
    def test_unauthorized_raises_401(self):
        """unauthorized raises HTTPException with 401"""
        with pytest.raises(HTTPException) as exc_info:
            unauthorized()
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.headers.get("WWW-Authenticate") == "Bearer"
    
    def test_bad_request_raises_400(self):
        """bad_request raises HTTPException with 400"""
        with pytest.raises(HTTPException) as exc_info:
            bad_request("Invalid input")
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid input"
    
    def test_conflict_raises_409(self):
        """conflict raises HTTPException with 409"""
        with pytest.raises(HTTPException) as exc_info:
            conflict("Duplicate entry")
        
        assert exc_info.value.status_code == 409
    
    def test_rate_limited_raises_429(self):
        """rate_limited raises HTTPException with 429"""
        with pytest.raises(HTTPException) as exc_info:
            rate_limited("Too many requests", retry_after=60)
        
        assert exc_info.value.status_code == 429
        assert exc_info.value.headers.get("Retry-After") == "60"
    
    def test_server_error_raises_500(self):
        """server_error raises HTTPException with 500"""
        with pytest.raises(HTTPException) as exc_info:
            server_error("Database connection failed")
        
        assert exc_info.value.status_code == 500


class TestSuccessResponses:
    """Tests for success response helpers."""
    
    def test_success_response_basic(self):
        """Basic success response"""
        response = success_response()
        
        assert response["status"] == "success"
    
    def test_success_response_with_data(self):
        """Success response with data"""
        data = {"id": 1, "name": "Test"}
        response = success_response(data=data)
        
        assert response["status"] == "success"
        assert response["data"] == data
    
    def test_success_response_with_message(self):
        """Success response with message"""
        response = success_response(message="Operation completed")
        
        assert response["status"] == "success"
        assert response["message"] == "Operation completed"
    
    def test_success_response_with_meta(self):
        """Success response with metadata"""
        meta = {"total": 100, "page": 1}
        response = success_response(data=[], meta=meta)
        
        assert response["status"] == "success"
        assert response["meta"] == meta
    
    def test_success_response_full(self):
        """Full success response with all fields"""
        response = success_response(
            data={"id": 1},
            message="Created",
            meta={"timestamp": "2024-01-01"}
        )
        
        assert response["status"] == "success"
        assert response["message"] == "Created"
        assert response["data"] == {"id": 1}
        assert response["meta"] == {"timestamp": "2024-01-01"}


class TestPaginatedResponse:
    """Tests for paginated response helper."""
    
    def test_paginated_response_first_page(self):
        """Paginated response for first page"""
        items = [1, 2, 3, 4, 5]
        response = paginated_response(items=items, total=100, page=1, size=5)
        
        assert response["items"] == items
        assert response["total"] == 100
        assert response["page"] == 1
        assert response["size"] == 5
        assert response["pages"] == 20
        assert response["has_next"] is True
        assert response["has_prev"] is False
    
    def test_paginated_response_middle_page(self):
        """Paginated response for middle page"""
        response = paginated_response(items=[], total=100, page=5, size=10)
        
        assert response["page"] == 5
        assert response["pages"] == 10
        assert response["has_next"] is True
        assert response["has_prev"] is True
    
    def test_paginated_response_last_page(self):
        """Paginated response for last page"""
        response = paginated_response(items=[], total=100, page=10, size=10)
        
        assert response["has_next"] is False
        assert response["has_prev"] is True
    
    def test_paginated_response_single_page(self):
        """Paginated response with single page"""
        response = paginated_response(items=[1, 2], total=2, page=1, size=10)
        
        assert response["pages"] == 1
        assert response["has_next"] is False
        assert response["has_prev"] is False


class TestConvenienceMethods:
    """Tests for convenience response methods."""
    
    def test_created_response(self):
        """created_response convenience method"""
        data = {"id": 1}
        response = created_response(data)
        
        assert response["status"] == "success"
        assert response["data"] == data
        assert "создано" in response["message"].lower() or "created" in response["message"].lower()
    
    def test_updated_response(self):
        """updated_response convenience method"""
        data = {"id": 1, "name": "Updated"}
        response = updated_response(data)
        
        assert response["status"] == "success"
        assert response["data"] == data
    
    def test_deleted_response(self):
        """deleted_response convenience method"""
        response = deleted_response()
        
        assert response["status"] == "success"
        assert "удалено" in response["message"].lower() or "deleted" in response["message"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
