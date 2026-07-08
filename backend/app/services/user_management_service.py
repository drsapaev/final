"""Backward-compatible shim for user_mgmt package."""
from __future__ import annotations
from app.services.user_mgmt import UserManagementService
from app.services.user_mgmt._operations import get_user_management_service

user_management_service = UserManagementService()

__all__ = ["UserManagementService", "user_management_service", "get_user_management_service"]
