"""
Monitoring Configuration

✅ SECURITY: Monitoring setup for production system
"""
import logging
import os
from typing import Dict, Optional

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/app.log", encoding="utf-8") if os.path.exists("logs") else logging.NullHandler(),
    ],
)

logger = logging.getLogger(__name__)


class MonitoringConfig:
    """Monitoring configuration"""

    # Health check endpoints
    HEALTH_CHECK_ENDPOINTS = [
        "/api/v1/health",
        "/api/v1/system/status",
    ]

    # Metrics to track
    METRICS = {
        "api_requests_total": "counter",
        "api_requests_duration": "histogram",
        "api_errors_total": "counter",
        "database_queries_total": "counter",
        "database_queries_duration": "histogram",
        "websocket_connections": "gauge",
        "websocket_messages_total": "counter",
        "payment_webhooks_total": "counter",
        "payment_webhooks_failed": "counter",
        "backup_operations_total": "counter",
        "backup_operations_failed": "counter",
    }

    # Alert thresholds
    ALERT_THRESHOLDS = {
        "api_error_rate": 0.05,  # 5% error rate
        "api_response_time_p95": 2000,  # 2 seconds
        "database_query_time": 1000,  # 1 second
        "websocket_disconnect_rate": 0.1,  # 10%
        "payment_webhook_failure_rate": 0.01,  # 1%
        "backup_failure_rate": 0.05,  # 5%
    }

    @staticmethod
    def get_sentry_config() -> Optional[Dict]:
        """Get Sentry configuration if available"""
        sentry_dsn = os.getenv("SENTRY_DSN")
        if sentry_dsn:
            return {
                "dsn": sentry_dsn,
                "environment": os.getenv("ENV", "dev"),
                "traces_sample_rate": float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
                "profiles_sample_rate": float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),
            }
        return None

    @staticmethod
    def setup_sentry():
        """Setup Sentry error tracking"""
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

            config = MonitoringConfig.get_sentry_config()
            if config:
                sentry_sdk.init(
                    dsn=config["dsn"],
                    environment=config["environment"],
                    traces_sample_rate=config["traces_sample_rate"],
                    profiles_sample_rate=config["profiles_sample_rate"],
                    integrations=[
                        FastApiIntegration(),
                        SqlalchemyIntegration(),
                    ],
                )
                logger.info("✅ Sentry initialized for error tracking")
            else:
                logger.info("ℹ️  Sentry DSN not configured, skipping Sentry setup")
        except ImportError:
            logger.warning("⚠️  Sentry SDK not installed, skipping Sentry setup")
        except Exception as e:
            logger.error(f"❌ Error setting up Sentry: {e}")

    @staticmethod
    def get_prometheus_config() -> Dict:
        """Get Prometheus metrics configuration"""
        return {
            "enabled": os.getenv("PROMETHEUS_ENABLED", "false").lower() == "true",
            "port": int(os.getenv("PROMETHEUS_PORT", "9090")),
            "path": os.getenv("PROMETHEUS_PATH", "/metrics"),
        }

    @staticmethod
    def setup_prometheus():
        """Setup Prometheus metrics"""
        try:
            from prometheus_client import Counter, Histogram, Gauge, start_http_server

            config = MonitoringConfig.get_prometheus_config()
            if config["enabled"]:
                # Create metrics
                metrics = {}
                for metric_name, metric_type in MonitoringConfig.METRICS.items():
                    if metric_type == "counter":
                        metrics[metric_name] = Counter(metric_name, f"{metric_name} description")
                    elif metric_type == "histogram":
                        metrics[metric_name] = Histogram(
                            metric_name, f"{metric_name} description", buckets=[0.1, 0.5, 1, 2, 5, 10]
                        )
                    elif metric_type == "gauge":
                        metrics[metric_name] = Gauge(metric_name, f"{metric_name} description")

                # Start metrics server
                start_http_server(config["port"])
                logger.info(f"✅ Prometheus metrics server started on port {config['port']}")
                return metrics
            else:
                logger.info("ℹ️  Prometheus not enabled")
                return {}
        except ImportError:
            logger.warning("⚠️  Prometheus client not installed, skipping Prometheus setup")
            return {}
        except Exception as e:
            logger.error(f"❌ Error setting up Prometheus: {e}")
            return {}

    @staticmethod
    def setup_logging():
        """Setup structured logging"""
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)

        # Configure file handler
        file_handler = logging.FileHandler("logs/app.log", encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)

        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)

        logger.info("✅ Logging configured")

    @staticmethod
    def initialize():
        """Initialize all monitoring components"""
        logger.info("Initializing monitoring...")

        MonitoringConfig.setup_logging()
        MonitoringConfig.setup_sentry()
        metrics = MonitoringConfig.setup_prometheus()

        logger.info("✅ Monitoring initialized")
        return metrics


# Initialize on import
if __name__ != "__main__":
    monitoring_metrics = MonitoringConfig.initialize()


