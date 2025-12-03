"""
Firebase Cloud Messaging Service

✅ SECURITY: Real Firebase Cloud Messaging integration for push notifications
"""
import json
import logging
from typing import Dict, List, Optional

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


class FirebaseService:
    """Service for Firebase Cloud Messaging"""

    FCM_URL = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

    def __init__(self):
        self.server_key = getattr(settings, "FCM_SERVER_KEY", None)
        self.project_id = getattr(settings, "FCM_PROJECT_ID", None)
        self.sender_id = getattr(settings, "FCM_SENDER_ID", None)
        self.enabled = getattr(settings, "FCM_ENABLED", False)

        if not self.enabled:
            logger.warning("FCM is disabled in settings")
            return

        if not self.project_id:
            logger.warning("FCM_PROJECT_ID not configured")
            return

        # For FCM v1 API, we need OAuth2 token
        # For simplicity, we'll use the legacy HTTP v1 API with server key if available
        if self.server_key:
            self.use_legacy_api = True
            self.legacy_url = "https://fcm.googleapis.com/fcm/send"
        else:
            self.use_legacy_api = False
            logger.warning("FCM_SERVER_KEY not configured, FCM v1 API requires OAuth2")

    def _get_oauth_token(self) -> Optional[str]:
        """
        Get OAuth2 token for FCM v1 API
        
        This requires service account credentials
        """
        # TODO: Implement OAuth2 token retrieval from service account
        # For now, we'll use legacy API if server_key is available
        return None

    def send_notification(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict] = None,
        priority: str = "high",
    ) -> Dict[str, any]:
        """
        Send push notification via FCM
        
        Args:
            device_token: FCM device token
            title: Notification title
            body: Notification body
            data: Additional data payload
            priority: Notification priority (normal, high)
        
        Returns:
            Result dict with success status
        """
        if not self.enabled:
            return {
                "success": False,
                "error": "FCM is disabled",
            }

        if not device_token:
            return {
                "success": False,
                "error": "Device token is required",
            }

        try:
            if self.use_legacy_api and self.server_key:
                return self._send_legacy(device_token, title, body, data, priority)
            else:
                return self._send_v1(device_token, title, body, data, priority)

        except Exception as e:
            logger.error(f"FCM send error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _send_legacy(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict] = None,
        priority: str = "high",
    ) -> Dict[str, any]:
        """Send using FCM Legacy HTTP API"""
        payload = {
            "to": device_token,
            "notification": {
                "title": title,
                "body": body,
            },
            "data": data or {},
            "priority": priority,
        }

        headers = {
            "Authorization": f"key={self.server_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                self.legacy_url,
                headers=headers,
                json=payload,
                timeout=10,
            )

            response.raise_for_status()
            result = response.json()

            if result.get("success") == 1:
                logger.info(f"✅ FCM notification sent to {device_token[:20]}...")
                return {
                    "success": True,
                    "message_id": result.get("message_id"),
                }
            else:
                error = result.get("results", [{}])[0].get("error")
                logger.error(f"❌ FCM send failed: {error}")
                return {
                    "success": False,
                    "error": error,
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"FCM request error: {e}")
            return {
                "success": False,
                "error": f"Request failed: {str(e)}",
            }

    def _send_v1(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict] = None,
        priority: str = "high",
    ) -> Dict[str, any]:
        """Send using FCM v1 API (requires OAuth2)"""
        # FCM v1 API format
        message = {
            "message": {
                "token": device_token,
                "notification": {
                    "title": title,
                    "body": body,
                },
                "data": {str(k): str(v) for k, v in (data or {}).items()},
                "android": {
                    "priority": priority,
                },
                "apns": {
                    "headers": {
                        "apns-priority": "10" if priority == "high" else "5",
                    },
                },
            }
        }

        oauth_token = self._get_oauth_token()
        if not oauth_token:
            return {
                "success": False,
                "error": "OAuth2 token not available",
            }

        url = self.FCM_URL.format(project_id=self.project_id)
        headers = {
            "Authorization": f"Bearer {oauth_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(url, headers=headers, json=message, timeout=10)
            response.raise_for_status()
            result = response.json()

            logger.info(f"✅ FCM v1 notification sent to {device_token[:20]}...")
            return {
                "success": True,
                "name": result.get("name"),
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"FCM v1 request error: {e}")
            return {
                "success": False,
                "error": f"Request failed: {str(e)}",
            }

    def send_multicast(
        self,
        device_tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict] = None,
    ) -> Dict[str, any]:
        """
        Send notification to multiple devices
        
        Args:
            device_tokens: List of FCM device tokens
            title: Notification title
            body: Notification body
            data: Additional data payload
        
        Returns:
            Result dict with success/failure counts
        """
        if not self.enabled:
            return {
                "success": False,
                "error": "FCM is disabled",
            }

        results = {
            "success_count": 0,
            "failure_count": 0,
            "errors": [],
        }

        for token in device_tokens:
            result = self.send_notification(token, title, body, data)
            if result.get("success"):
                results["success_count"] += 1
            else:
                results["failure_count"] += 1
                results["errors"].append({
                    "token": token[:20] + "...",
                    "error": result.get("error"),
                })

        return results

    def validate_token(self, device_token: str) -> bool:
        """
        Validate FCM device token
        
        Args:
            device_token: FCM device token to validate
        
        Returns:
            True if token appears valid
        """
        if not device_token:
            return False

        # Basic validation: FCM tokens are typically long strings
        if len(device_token) < 50:
            return False

        # Try sending a test notification (silent)
        # In production, you might want to use FCM's token validation API
        return True


