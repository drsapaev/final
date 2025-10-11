"""
MCP Configuration Settings
"""
from pydantic import BaseSettings
from typing import Optional


class MCPSettings(BaseSettings):
    """Настройки для MCP (Model Context Protocol)"""
    
    # Основные настройки
    MCP_ENABLED: bool = True
    MCP_LOG_REQUESTS: bool = True
    MCP_FALLBACK_TO_DIRECT: bool = True
    
    # Таймауты и лимиты
    MCP_REQUEST_TIMEOUT: int = 120  # секунды (увеличен для AI запросов)
    MCP_HEALTH_CHECK_INTERVAL: int = 60  # секунды
    MCP_MAX_BATCH_SIZE: int = 10
    
    # Настройки серверов
    MCP_COMPLAINT_SERVER_ENABLED: bool = True
    MCP_ICD10_SERVER_ENABLED: bool = True
    MCP_LAB_SERVER_ENABLED: bool = True
    MCP_IMAGING_SERVER_ENABLED: bool = True
    
    # Настройки мониторинга
    MCP_METRICS_ENABLED: bool = True
    MCP_METRICS_RETENTION_DAYS: int = 30
    
    # Настройки безопасности
    MCP_MAX_IMAGE_SIZE_MB: int = 25
    MCP_ALLOWED_IMAGE_TYPES: list = ["image/jpeg", "image/png", "image/heic"]
    MCP_MAX_REQUEST_SIZE_MB: int = 50
    
    # Настройки AI провайдеров через MCP
    MCP_DEFAULT_AI_PROVIDER: Optional[str] = None  # None = auto-select
    MCP_PREFER_OPENAI_FOR_IMAGES: bool = True
    MCP_PREFER_GEMINI_FOR_ANALYSIS: bool = False
    
    class Config:
        case_sensitive = True
        env_file = ".env"


mcp_settings = MCPSettings()
