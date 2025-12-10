"""
Critical Error Alerts System

This module provides alerting functionality for critical system events:
- Payment failures
- Database connection errors
- Authentication failures
- High error rates
- Queue system failures

Integration points:
- Sentry (already integrated in main.py)
- Telegram notifications (optional)
- Email alerts (optional)
- Webhook callbacks (optional)
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of alerts"""
    PAYMENT_FAILURE = "payment_failure"
    DATABASE_ERROR = "database_error"
    AUTH_FAILURE = "auth_failure"
    QUEUE_ERROR = "queue_error"
    HIGH_ERROR_RATE = "high_error_rate"
    EXTERNAL_SERVICE = "external_service"
    SECURITY_INCIDENT = "security_incident"
    SYSTEM_RESOURCE = "system_resource"


@dataclass
class Alert:
    """Alert data structure"""
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class AlertThresholds:
    """Configurable alert thresholds"""
    
    # Error rate thresholds (errors per minute)
    ERROR_RATE_WARNING = 10
    ERROR_RATE_CRITICAL = 50
    
    # Authentication failure thresholds (per 5 minutes)
    AUTH_FAILURE_WARNING = 10
    AUTH_FAILURE_CRITICAL = 50
    
    # Payment failure thresholds (per hour)
    PAYMENT_FAILURE_WARNING = 3
    PAYMENT_FAILURE_CRITICAL = 10
    
    # Queue processing thresholds (seconds)
    QUEUE_PROCESSING_WARNING = 60
    QUEUE_PROCESSING_CRITICAL = 300
    
    # Database connection timeout (seconds)
    DB_CONNECTION_TIMEOUT = 5


class AlertManager:
    """
    Centralized alert management system.
    
    Features:
    - Collects alerts from various sources
    - Deduplicates repeated alerts
    - Tracks alert history
    - Sends notifications through configured channels
    """
    
    def __init__(self):
        self._alerts: List[Alert] = []
        self._alert_counts: Dict[AlertType, int] = defaultdict(int)
        self._last_alert_time: Dict[AlertType, datetime] = {}
        self._handlers: List[Callable[[Alert], None]] = []
        self._cooldown_minutes = 5  # Minimum time between same type alerts
        
        # Error rate tracking
        self._error_timestamps: List[datetime] = []
        self._auth_failure_timestamps: List[datetime] = []
        self._payment_failure_timestamps: List[datetime] = []
    
    def register_handler(self, handler: Callable[[Alert], None]) -> None:
        """Register an alert handler (e.g., email, Telegram, webhook)"""
        self._handlers.append(handler)
    
    def _should_alert(self, alert_type: AlertType) -> bool:
        """Check if we should send this alert (cooldown check)"""
        last_time = self._last_alert_time.get(alert_type)
        if not last_time:
            return True
        
        cooldown = timedelta(minutes=self._cooldown_minutes)
        return datetime.utcnow() - last_time > cooldown
    
    def _send_alert(self, alert: Alert) -> None:
        """Send alert through all registered handlers"""
        for handler in self._handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")
    
    def create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> Optional[Alert]:
        """
        Create and dispatch an alert.
        
        Args:
            alert_type: Type of alert
            severity: Severity level
            message: Human-readable message
            details: Additional context
            force: Skip cooldown check
        
        Returns:
            Alert object if created, None if suppressed
        """
        if not force and not self._should_alert(alert_type):
            logger.debug(f"Alert suppressed (cooldown): {alert_type}")
            return None
        
        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            message=message,
            details=details or {}
        )
        
        self._alerts.append(alert)
        self._alert_counts[alert_type] += 1
        self._last_alert_time[alert_type] = datetime.utcnow()
        
        # Log the alert
        log_method = getattr(logger, severity.value, logger.error)
        log_method(f"ALERT [{alert_type.value}]: {message}", extra=details or {})
        
        # Send Sentry event for errors and critical
        if severity in (AlertSeverity.ERROR, AlertSeverity.CRITICAL):
            try:
                import sentry_sdk
                sentry_sdk.capture_message(
                    f"[{severity.value.upper()}] {message}",
                    level=severity.value
                )
            except ImportError:
                pass
        
        # Dispatch to handlers
        self._send_alert(alert)
        
        return alert
    
    # === Convenience methods for common alerts ===
    
    def payment_failure(self, payment_id: str, error: str, amount: float = 0) -> None:
        """Alert for payment processing failure"""
        self._payment_failure_timestamps.append(datetime.utcnow())
        self._cleanup_old_timestamps()
        
        # Check threshold
        recent_failures = len([
            t for t in self._payment_failure_timestamps
            if datetime.utcnow() - t < timedelta(hours=1)
        ])
        
        if recent_failures >= AlertThresholds.PAYMENT_FAILURE_CRITICAL:
            severity = AlertSeverity.CRITICAL
        elif recent_failures >= AlertThresholds.PAYMENT_FAILURE_WARNING:
            severity = AlertSeverity.WARNING
        else:
            severity = AlertSeverity.ERROR
        
        self.create_alert(
            AlertType.PAYMENT_FAILURE,
            severity,
            f"Payment failed: {error}",
            {
                "payment_id": payment_id,
                "amount": amount,
                "error": error,
                "recent_failures": recent_failures
            }
        )
    
    def database_error(self, error: str, query: Optional[str] = None) -> None:
        """Alert for database connection/query errors"""
        self.create_alert(
            AlertType.DATABASE_ERROR,
            AlertSeverity.CRITICAL,
            f"Database error: {error}",
            {"error": error, "query": query[:200] if query else None}
        )
    
    def auth_failure(self, username: str, ip: str, reason: str) -> None:
        """Alert for authentication failures (brute force detection)"""
        self._auth_failure_timestamps.append(datetime.utcnow())
        self._cleanup_old_timestamps()
        
        recent_failures = len([
            t for t in self._auth_failure_timestamps
            if datetime.utcnow() - t < timedelta(minutes=5)
        ])
        
        if recent_failures >= AlertThresholds.AUTH_FAILURE_CRITICAL:
            self.create_alert(
                AlertType.AUTH_FAILURE,
                AlertSeverity.CRITICAL,
                f"Possible brute force attack: {recent_failures} failed attempts",
                {"username": username, "ip": ip, "reason": reason, "count": recent_failures}
            )
        elif recent_failures >= AlertThresholds.AUTH_FAILURE_WARNING:
            self.create_alert(
                AlertType.AUTH_FAILURE,
                AlertSeverity.WARNING,
                f"Multiple auth failures: {recent_failures} attempts",
                {"username": username, "ip": ip, "reason": reason, "count": recent_failures}
            )
    
    def queue_error(self, queue_name: str, error: str) -> None:
        """Alert for queue processing errors"""
        self.create_alert(
            AlertType.QUEUE_ERROR,
            AlertSeverity.ERROR,
            f"Queue error in {queue_name}: {error}",
            {"queue": queue_name, "error": error}
        )
    
    def security_incident(self, incident_type: str, details: Dict[str, Any]) -> None:
        """Alert for security incidents"""
        self.create_alert(
            AlertType.SECURITY_INCIDENT,
            AlertSeverity.CRITICAL,
            f"Security incident: {incident_type}",
            details,
            force=True  # Always send security alerts
        )
    
    def external_service_error(self, service: str, error: str) -> None:
        """Alert for external service failures (Telegram, FCM, etc.)"""
        self.create_alert(
            AlertType.EXTERNAL_SERVICE,
            AlertSeverity.WARNING,
            f"External service error ({service}): {error}",
            {"service": service, "error": error}
        )
    
    def track_error(self) -> None:
        """Track an error for error rate monitoring"""
        self._error_timestamps.append(datetime.utcnow())
        self._cleanup_old_timestamps()
        
        errors_per_minute = len([
            t for t in self._error_timestamps
            if datetime.utcnow() - t < timedelta(minutes=1)
        ])
        
        if errors_per_minute >= AlertThresholds.ERROR_RATE_CRITICAL:
            self.create_alert(
                AlertType.HIGH_ERROR_RATE,
                AlertSeverity.CRITICAL,
                f"Critical error rate: {errors_per_minute} errors/minute",
                {"errors_per_minute": errors_per_minute}
            )
        elif errors_per_minute >= AlertThresholds.ERROR_RATE_WARNING:
            self.create_alert(
                AlertType.HIGH_ERROR_RATE,
                AlertSeverity.WARNING,
                f"High error rate: {errors_per_minute} errors/minute",
                {"errors_per_minute": errors_per_minute}
            )
    
    def _cleanup_old_timestamps(self) -> None:
        """Remove timestamps older than 1 hour"""
        cutoff = datetime.utcnow() - timedelta(hours=1)
        self._error_timestamps = [t for t in self._error_timestamps if t > cutoff]
        self._auth_failure_timestamps = [t for t in self._auth_failure_timestamps if t > cutoff]
        self._payment_failure_timestamps = [t for t in self._payment_failure_timestamps if t > cutoff]
    
    def get_recent_alerts(self, hours: int = 24) -> List[Alert]:
        """Get alerts from the last N hours"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [a for a in self._alerts if a.timestamp > cutoff]
    
    def get_alert_stats(self) -> Dict[str, Any]:
        """Get alert statistics"""
        return {
            "total_alerts": len(self._alerts),
            "alerts_by_type": dict(self._alert_counts),
            "recent_24h": len(self.get_recent_alerts(24)),
            "unresolved": len([a for a in self._alerts if not a.resolved])
        }


# Global alert manager instance
alert_manager = AlertManager()


# === Alert Handlers ===

def log_alert_handler(alert: Alert) -> None:
    """Simple logging handler"""
    logger.info(
        f"[ALERT] {alert.severity.value.upper()} - {alert.alert_type.value}: {alert.message}",
        extra=alert.details
    )


def sentry_alert_handler(alert: Alert) -> None:
    """Send alert to Sentry"""
    try:
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("alert_type", alert.alert_type.value)
            scope.set_tag("severity", alert.severity.value)
            for key, value in alert.details.items():
                scope.set_extra(key, value)
            
            if alert.severity == AlertSeverity.CRITICAL:
                sentry_sdk.capture_message(alert.message, level="fatal")
            else:
                sentry_sdk.capture_message(alert.message, level=alert.severity.value)
    except ImportError:
        pass


# Register default handlers
alert_manager.register_handler(log_alert_handler)
alert_manager.register_handler(sentry_alert_handler)


# === Decorator for automatic error tracking ===

def track_errors(func: Callable) -> Callable:
    """Decorator to automatically track errors for rate monitoring"""
    from functools import wraps
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            alert_manager.track_error()
            raise
    
    return wrapper
