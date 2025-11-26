"""
MCP Manager - централизованное управление MCP сервисами
"""
from typing import Dict, Any, Optional, List
import asyncio
import logging
from datetime import datetime, timedelta
from .mcp_client import MedicalMCPClient, get_mcp_client, shutdown_mcp_client
from ...core.config import settings

logger = logging.getLogger(__name__)


class MCPManager:
    """Менеджер для управления MCP сервисами и мониторинга"""
    
    def __init__(self):
        self.client: Optional[MedicalMCPClient] = None
        self.metrics: Dict[str, Any] = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_failed": 0,
            "server_stats": {},
            "last_health_check": None
        }
        self.config = self._load_config()
        self._health_check_task: Optional[asyncio.Task] = None
    
    def _load_config(self) -> Dict[str, Any]:
        """Загрузка конфигурации MCP"""
        return {
            "enabled": getattr(settings, "MCP_ENABLED", True),
            "health_check_interval": getattr(settings, "MCP_HEALTH_CHECK_INTERVAL", 60),  # секунды
            "request_timeout": getattr(settings, "MCP_REQUEST_TIMEOUT", 30),  # секунды
            "max_batch_size": getattr(settings, "MCP_MAX_BATCH_SIZE", 10),
            "fallback_to_direct": getattr(settings, "MCP_FALLBACK_TO_DIRECT", True),
            "log_requests": getattr(settings, "MCP_LOG_REQUESTS", True)
        }
    
    async def initialize(self):
        """Инициализация MCP менеджера"""
        if not self.config["enabled"]:
            logger.info("MCP is disabled in configuration")
            return
        
        try:
            self.client = await get_mcp_client()
            logger.info("MCP Manager initialized successfully")
            
            # Запускаем периодическую проверку здоровья
            if self.config["health_check_interval"] > 0:
                self._health_check_task = asyncio.create_task(
                    self._periodic_health_check()
                )
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP Manager: {str(e)}")
            if not self.config["fallback_to_direct"]:
                raise
    
    async def shutdown(self):
        """Завершение работы MCP менеджера"""
        try:
            # Отменяем задачу проверки здоровья
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass
            
            # Завершаем работу клиента
            if self.client:
                await shutdown_mcp_client()
                self.client = None
            
            logger.info("MCP Manager shut down successfully")
            
        except Exception as e:
            logger.error(f"Error shutting down MCP Manager: {str(e)}")
    
    async def _periodic_health_check(self):
        """Периодическая проверка состояния серверов"""
        while True:
            try:
                await asyncio.sleep(self.config["health_check_interval"])
                
                if self.client:
                    health_status = await self.client.health_check()
                    self.metrics["last_health_check"] = health_status
                    
                    # Обновляем метрики серверов
                    for server_name, status in health_status.get("servers", {}).items():
                        if server_name not in self.metrics["server_stats"]:
                            self.metrics["server_stats"][server_name] = {
                                "requests": 0,
                                "errors": 0,
                                "avg_response_time": 0
                            }
                        
                        self.metrics["server_stats"][server_name]["healthy"] = (
                            status.get("status") == "healthy"
                        )
                    
                    if health_status.get("overall") != "healthy":
                        logger.warning(f"MCP health check: {health_status.get('overall')}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check: {str(e)}")
    
    async def execute_request(
        self,
        server: str,
        method: str,
        params: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Выполнение запроса через MCP
        
        Args:
            server: Имя сервера (complaint, icd10, lab, imaging)
            method: Метод для вызова
            params: Параметры запроса
            timeout: Таймаут запроса
        
        Returns:
            Результат выполнения
        """
        if not self.config["enabled"] or not self.client:
            return {
                "status": "error",
                "error": "MCP is not available",
                "fallback": self.config["fallback_to_direct"]
            }
        
        start_time = datetime.utcnow()
        timeout = timeout or self.config["request_timeout"]
        
        try:
            # Логируем запрос если включено
            if self.config["log_requests"]:
                logger.debug(f"MCP request: {server}.{method}")
            
            # Выполняем запрос с таймаутом
            result = await asyncio.wait_for(
                self.client._call_server(server, method, params),
                timeout=timeout
            )
            
            # Обновляем метрики
            self.metrics["requests_total"] += 1
            if result.get("status") == "success":
                self.metrics["requests_success"] += 1
            else:
                self.metrics["requests_failed"] += 1
            
            # Обновляем статистику сервера
            if server not in self.metrics["server_stats"]:
                self.metrics["server_stats"][server] = {
                    "requests": 0,
                    "errors": 0,
                    "avg_response_time": 0
                }
            
            server_stats = self.metrics["server_stats"][server]
            server_stats["requests"] += 1
            
            if result.get("status") != "success":
                server_stats["errors"] += 1
            
            # Обновляем среднее время ответа
            response_time = (datetime.utcnow() - start_time).total_seconds()
            current_avg = server_stats["avg_response_time"]
            total_requests = server_stats["requests"]
            server_stats["avg_response_time"] = (
                (current_avg * (total_requests - 1) + response_time) / total_requests
            )
            
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"MCP request timeout: {server}.{method}")
            self.metrics["requests_failed"] += 1
            
            return {
                "status": "error",
                "error": "Request timeout",
                "timeout": timeout
            }
            
        except Exception as e:
            logger.error(f"MCP request error: {server}.{method} - {str(e)}")
            self.metrics["requests_failed"] += 1
            
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def batch_execute(
        self,
        requests: List[Dict[str, Any]],
        parallel: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Пакетное выполнение запросов
        
        Args:
            requests: Список запросов
            parallel: Выполнять параллельно
        
        Returns:
            Список результатов
        """
        if not self.config["enabled"] or not self.client:
            return [{
                "status": "error",
                "error": "MCP is not available"
            } for _ in requests]
        
        # Ограничиваем размер пакета
        if len(requests) > self.config["max_batch_size"]:
            logger.warning(
                f"Batch size {len(requests)} exceeds limit {self.config['max_batch_size']}"
            )
            requests = requests[:self.config["max_batch_size"]]
        
        if parallel:
            # Параллельное выполнение
            tasks = [
                self.execute_request(
                    req.get("server"),
                    req.get("method"),
                    req.get("params", {})
                )
                for req in requests
            ]
            return await asyncio.gather(*tasks)
        else:
            # Последовательное выполнение
            results = []
            for req in requests:
                result = await self.execute_request(
                    req.get("server"),
                    req.get("method"),
                    req.get("params", {})
                )
                results.append(result)
            return results
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получение метрик MCP"""
        return {
            **self.metrics,
            "config": self.config,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_server_metrics(self, server_name: Optional[str] = None) -> Dict[str, Any]:
        """Получение метрик конкретного сервера"""
        if server_name:
            return self.metrics["server_stats"].get(server_name, {
                "error": f"No metrics for server {server_name}"
            })
        return self.metrics["server_stats"]
    
    async def get_capabilities(self) -> Dict[str, Any]:
        """Получение возможностей всех серверов"""
        if not self.client:
            return {
                "status": "error",
                "error": "MCP client not initialized"
            }
        
        return await self.client.get_server_capabilities()
    
    def is_healthy(self) -> bool:
        """Проверка здоровья MCP"""
        if not self.config["enabled"] or not self.client:
            return False
        
        last_check = self.metrics.get("last_health_check")
        if not last_check:
            return False
        
        return last_check.get("overall") == "healthy"
    
    async def reset_metrics(self):
        """Сброс метрик"""
        self.metrics = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_failed": 0,
            "server_stats": {},
            "last_health_check": None
        }
        logger.info("MCP metrics reset")


# Глобальный экземпляр менеджера
_mcp_manager: Optional[MCPManager] = None


async def get_mcp_manager() -> MCPManager:
    """Получить или создать глобальный экземпляр MCP менеджера"""
    global _mcp_manager
    
    if _mcp_manager is None:
        _mcp_manager = MCPManager()
        await _mcp_manager.initialize()
    
    return _mcp_manager


async def shutdown_mcp_manager():
    """Завершить работу MCP менеджера"""
    global _mcp_manager
    
    if _mcp_manager is not None:
        await _mcp_manager.shutdown()
        _mcp_manager = None
