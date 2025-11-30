"""
Сервис мониторинга системы
"""
import logging
import psutil
import time
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from pathlib import Path
import json

from app.core.config import settings
from app.db.session import get_db

logger = logging.getLogger(__name__)


class MonitoringService:
    """Сервис мониторинга системы"""
    
    def __init__(self):
        self.metrics_history = []
        self.alerts = []
        self.max_history_size = 1000
        
        # Пороговые значения для алертов
        self.thresholds = {
            "cpu_usage": 80.0,  # %
            "memory_usage": 85.0,  # %
            "disk_usage": 90.0,  # %
            "response_time": 5.0,  # секунды
            "error_rate": 10.0,  # %
            "database_connections": 50  # количество
        }
    
    # ===================== СБОР МЕТРИК =====================
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Получает текущие системные метрики"""
        try:
            # CPU метрики
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # Память
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Диск
            disk = psutil.disk_usage('/')
            
            # Сеть
            network = psutil.net_io_counters()
            
            # Процессы
            process_count = len(psutil.pids())
            
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "cpu": {
                    "usage_percent": cpu_percent,
                    "count": cpu_count,
                    "frequency": cpu_freq.current if cpu_freq else None
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "usage_percent": memory.percent,
                    "swap_total": swap.total,
                    "swap_used": swap.used,
                    "swap_percent": swap.percent
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "usage_percent": (disk.used / disk.total) * 100
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv
                },
                "processes": {
                    "count": process_count
                }
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Ошибка получения системных метрик: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}
    
    def get_application_metrics(self) -> Dict[str, Any]:
        """Получает метрики приложения"""
        try:
            # Метрики базы данных
            db_metrics = self._get_database_metrics()
            
            # Метрики файловой системы
            fs_metrics = self._get_filesystem_metrics()
            
            # Метрики производительности
            perf_metrics = self._get_performance_metrics()
            
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "database": db_metrics,
                "filesystem": fs_metrics,
                "performance": perf_metrics
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Ошибка получения метрик приложения: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}
    
    def _get_database_metrics(self) -> Dict[str, Any]:
        """Получает метрики базы данных"""
        try:
            engine = create_engine(settings.DATABASE_URL)
            
            with engine.connect() as conn:
                # Количество активных соединений
                if "sqlite" in settings.DATABASE_URL:
                    # Для SQLite соединения не актуальны
                    active_connections = 1
                    
                    # Размер БД
                    db_file = settings.DATABASE_URL.replace("sqlite:///", "")
                    db_size = Path(db_file).stat().st_size if Path(db_file).exists() else 0
                    
                    # Количество таблиц
                    tables_result = conn.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type='table'"))
                    tables_count = tables_result.scalar()
                    
                else:
                    # Для PostgreSQL
                    conn_result = conn.execute(text("SELECT COUNT(*) FROM pg_stat_activity"))
                    active_connections = conn_result.scalar()
                    
                    # Размер БД
                    size_result = conn.execute(text("SELECT pg_database_size(current_database())"))
                    db_size = size_result.scalar()
                    
                    # Количество таблиц
                    tables_result = conn.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"))
                    tables_count = tables_result.scalar()
                
                # Количество записей в основных таблицах
                # Безопасно: используем предопределенный whitelist таблиц
                main_tables = ['patients', 'appointments', 'visits', 'users', 'services']
                records_count = {}
                total_records = 0
                
                for table in main_tables:
                    # Валидация: проверяем, что имя таблицы в whitelist и содержит только безопасные символы
                    if table not in main_tables or not all(c.isalnum() or c == '_' for c in table):
                        continue
                    try:
                        # Безопасно: используем предопределенное имя таблицы из whitelist
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        count = result.scalar()
                        records_count[table] = count
                        total_records += count
                    except:
                        records_count[table] = 0
                
                return {
                    "active_connections": active_connections,
                    "database_size": db_size,
                    "tables_count": tables_count,
                    "total_records": total_records,
                    "records_by_table": records_count,
                    "status": "healthy"
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения метрик БД: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _get_filesystem_metrics(self) -> Dict[str, Any]:
        """Получает метрики файловой системы"""
        try:
            # Размеры важных директорий
            directories = {
                "logs": "logs",
                "backups": "backups", 
                "reports": "reports",
                "uploads": "uploads"
            }
            
            dir_sizes = {}
            total_size = 0
            
            for name, path in directories.items():
                dir_path = Path(path)
                if dir_path.exists():
                    size = sum(f.stat().st_size for f in dir_path.rglob('*') if f.is_file())
                    dir_sizes[name] = size
                    total_size += size
                else:
                    dir_sizes[name] = 0
            
            # Количество файлов
            files_count = {}
            for name, path in directories.items():
                dir_path = Path(path)
                if dir_path.exists():
                    files_count[name] = len([f for f in dir_path.rglob('*') if f.is_file()])
                else:
                    files_count[name] = 0
            
            return {
                "directory_sizes": dir_sizes,
                "total_size": total_size,
                "files_count": files_count
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения метрик ФС: {e}")
            return {"error": str(e)}
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Получает метрики производительности"""
        try:
            # Время отклика БД
            start_time = time.time()
            try:
                engine = create_engine(settings.DATABASE_URL)
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                db_response_time = time.time() - start_time
            except:
                db_response_time = -1
            
            # Загрузка системы
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
            
            # Время работы системы
            boot_time = psutil.boot_time()
            uptime = time.time() - boot_time
            
            return {
                "database_response_time": db_response_time,
                "load_average": {
                    "1min": load_avg[0],
                    "5min": load_avg[1],
                    "15min": load_avg[2]
                },
                "system_uptime": uptime
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения метрик производительности: {e}")
            return {"error": str(e)}
    
    # ===================== АЛЕРТЫ И МОНИТОРИНГ =====================
    
    def check_health(self) -> Dict[str, Any]:
        """Проверяет общее состояние системы"""
        try:
            system_metrics = self.get_system_metrics()
            app_metrics = self.get_application_metrics()
            
            health_status = {
                "timestamp": datetime.now().isoformat(),
                "overall_status": "healthy",
                "components": {},
                "alerts": []
            }
            
            # Проверка системных ресурсов
            if "cpu" in system_metrics:
                cpu_usage = system_metrics["cpu"]["usage_percent"]
                if cpu_usage > self.thresholds["cpu_usage"]:
                    health_status["components"]["cpu"] = "critical"
                    health_status["alerts"].append({
                        "type": "cpu_high",
                        "message": f"Высокая загрузка CPU: {cpu_usage}%",
                        "severity": "critical"
                    })
                else:
                    health_status["components"]["cpu"] = "healthy"
            
            if "memory" in system_metrics:
                memory_usage = system_metrics["memory"]["usage_percent"]
                if memory_usage > self.thresholds["memory_usage"]:
                    health_status["components"]["memory"] = "critical"
                    health_status["alerts"].append({
                        "type": "memory_high",
                        "message": f"Высокое использование памяти: {memory_usage}%",
                        "severity": "critical"
                    })
                else:
                    health_status["components"]["memory"] = "healthy"
            
            if "disk" in system_metrics:
                disk_usage = system_metrics["disk"]["usage_percent"]
                if disk_usage > self.thresholds["disk_usage"]:
                    health_status["components"]["disk"] = "critical"
                    health_status["alerts"].append({
                        "type": "disk_full",
                        "message": f"Диск заполнен на {disk_usage:.1f}%",
                        "severity": "critical"
                    })
                else:
                    health_status["components"]["disk"] = "healthy"
            
            # Проверка базы данных
            if "database" in app_metrics and app_metrics["database"].get("status") == "healthy":
                health_status["components"]["database"] = "healthy"
                
                # Проверка времени отклика БД
                if "performance" in app_metrics:
                    db_response = app_metrics["performance"].get("database_response_time", 0)
                    if db_response > self.thresholds["response_time"]:
                        health_status["components"]["database"] = "warning"
                        health_status["alerts"].append({
                            "type": "db_slow",
                            "message": f"Медленный отклик БД: {db_response:.2f}с",
                            "severity": "warning"
                        })
            else:
                health_status["components"]["database"] = "critical"
                health_status["alerts"].append({
                    "type": "db_error",
                    "message": "Ошибка подключения к базе данных",
                    "severity": "critical"
                })
            
            # Определение общего статуса
            component_statuses = list(health_status["components"].values())
            if "critical" in component_statuses:
                health_status["overall_status"] = "critical"
            elif "warning" in component_statuses:
                health_status["overall_status"] = "warning"
            
            # Сохраняем алерты
            for alert in health_status["alerts"]:
                self._add_alert(alert)
            
            return health_status
            
        except Exception as e:
            logger.error(f"Ошибка проверки состояния системы: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "overall_status": "error",
                "error": str(e)
            }
    
    def get_alerts(self, severity: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Получает список алертов"""
        try:
            alerts = self.alerts.copy()
            
            if severity:
                alerts = [a for a in alerts if a.get("severity") == severity]
            
            # Сортируем по времени (новые первые)
            alerts.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            return alerts[:limit]
            
        except Exception as e:
            logger.error(f"Ошибка получения алертов: {e}")
            return []
    
    def _add_alert(self, alert: Dict[str, Any]):
        """Добавляет новый алерт"""
        try:
            alert["timestamp"] = datetime.now().isoformat()
            alert["id"] = f"{alert['type']}_{int(time.time())}"
            
            # Проверяем, нет ли уже такого алерта
            existing = [a for a in self.alerts if a.get("type") == alert["type"]]
            if not existing:
                self.alerts.append(alert)
                
                # Ограничиваем количество алертов
                if len(self.alerts) > 1000:
                    self.alerts = self.alerts[-500:]
                
                logger.warning(f"Новый алерт: {alert['message']}")
            
        except Exception as e:
            logger.error(f"Ошибка добавления алерта: {e}")
    
    # ===================== ИСТОРИЯ МЕТРИК =====================
    
    def collect_metrics(self):
        """Собирает и сохраняет метрики"""
        try:
            system_metrics = self.get_system_metrics()
            app_metrics = self.get_application_metrics()
            
            combined_metrics = {
                "timestamp": datetime.now().isoformat(),
                "system": system_metrics,
                "application": app_metrics
            }
            
            self.metrics_history.append(combined_metrics)
            
            # Ограничиваем размер истории
            if len(self.metrics_history) > self.max_history_size:
                self.metrics_history = self.metrics_history[-self.max_history_size//2:]
            
        except Exception as e:
            logger.error(f"Ошибка сбора метрик: {e}")
    
    def get_metrics_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Получает историю метрик за указанное количество часов"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            filtered_metrics = []
            for metric in self.metrics_history:
                try:
                    metric_time = datetime.fromisoformat(metric["timestamp"])
                    if metric_time >= cutoff_time:
                        filtered_metrics.append(metric)
                except:
                    continue
            
            return filtered_metrics
            
        except Exception as e:
            logger.error(f"Ошибка получения истории метрик: {e}")
            return []
    
    def get_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Получает сводку метрик за период"""
        try:
            history = self.get_metrics_history(hours)
            
            if not history:
                return {"error": "Нет данных за указанный период"}
            
            # Извлекаем значения для анализа
            cpu_values = []
            memory_values = []
            disk_values = []
            db_response_times = []
            
            for metric in history:
                if "system" in metric and isinstance(metric["system"], dict):
                    if "cpu" in metric["system"]:
                        cpu_values.append(metric["system"]["cpu"].get("usage_percent", 0))
                    if "memory" in metric["system"]:
                        memory_values.append(metric["system"]["memory"].get("usage_percent", 0))
                    if "disk" in metric["system"]:
                        disk_values.append(metric["system"]["disk"].get("usage_percent", 0))
                
                if "application" in metric and isinstance(metric["application"], dict):
                    if "performance" in metric["application"]:
                        db_time = metric["application"]["performance"].get("database_response_time", 0)
                        if db_time > 0:
                            db_response_times.append(db_time)
            
            summary = {
                "period_hours": hours,
                "data_points": len(history),
                "cpu": self._calculate_stats(cpu_values),
                "memory": self._calculate_stats(memory_values),
                "disk": self._calculate_stats(disk_values),
                "database_response_time": self._calculate_stats(db_response_times)
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Ошибка получения сводки метрик: {e}")
            return {"error": str(e)}
    
    def _calculate_stats(self, values: List[float]) -> Dict[str, float]:
        """Вычисляет статистики для списка значений"""
        if not values:
            return {"min": 0, "max": 0, "avg": 0, "current": 0}
        
        return {
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "current": values[-1] if values else 0
        }
    
    # ===================== АВТОМАТИЧЕСКИЙ МОНИТОРИНГ =====================
    
    async def start_monitoring(self, interval: int = 60):
        """Запускает автоматический мониторинг"""
        logger.info(f"Запуск мониторинга с интервалом {interval} секунд")
        
        while True:
            try:
                # Собираем метрики
                self.collect_metrics()
                
                # Проверяем состояние системы
                health = self.check_health()
                
                # Логируем критические проблемы
                if health.get("overall_status") == "critical":
                    logger.critical(f"Критическое состояние системы: {health.get('alerts', [])}")
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
                await asyncio.sleep(interval)
    
    # ===================== НАСТРОЙКИ =====================
    
    def update_thresholds(self, new_thresholds: Dict[str, float]) -> Dict[str, Any]:
        """Обновляет пороговые значения для алертов"""
        try:
            for key, value in new_thresholds.items():
                if key in self.thresholds:
                    self.thresholds[key] = value
            
            return {
                "success": True,
                "updated_thresholds": self.thresholds
            }
            
        except Exception as e:
            logger.error(f"Ошибка обновления порогов: {e}")
            return {"success": False, "error": str(e)}
    
    def get_thresholds(self) -> Dict[str, float]:
        """Получает текущие пороговые значения"""
        return self.thresholds.copy()


def get_monitoring_service() -> MonitoringService:
    """Получить экземпляр сервиса мониторинга"""
    return MonitoringService()

