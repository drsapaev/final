"""
Database Query Optimization Module

This module provides:
1. Query performance monitoring
2. Index recommendations
3. N+1 query detection
4. Slow query logging
5. Query statistics

Usage:
    from app.core.query_optimizer import QueryOptimizer, slow_query_logger

    # Enable in development
    QueryOptimizer.enable_slow_query_logging(threshold_ms=100)
"""

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable
from collections import defaultdict
from functools import wraps

from sqlalchemy import event, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


@dataclass
class QueryStats:
    """Statistics for a single query pattern"""
    query_pattern: str
    count: int = 0
    total_time_ms: float = 0
    min_time_ms: float = float('inf')
    max_time_ms: float = 0
    avg_time_ms: float = 0
    last_executed: Optional[datetime] = None
    
    def add_execution(self, time_ms: float) -> None:
        self.count += 1
        self.total_time_ms += time_ms
        self.min_time_ms = min(self.min_time_ms, time_ms)
        self.max_time_ms = max(self.max_time_ms, time_ms)
        self.avg_time_ms = self.total_time_ms / self.count
        self.last_executed = datetime.utcnow()


class QueryOptimizer:
    """
    Database query performance monitoring and optimization.
    
    Features:
    - Slow query detection and logging
    - Query statistics collection
    - N+1 query detection
    - Index recommendations
    """
    
    _instance = None
    _enabled = False
    _slow_query_threshold_ms = 100  # Default 100ms
    _query_stats: Dict[str, QueryStats] = {}
    _recent_queries: List[Dict[str, Any]] = []
    _n_plus_one_detection: Dict[str, List[datetime]] = defaultdict(list)
    
    @classmethod
    def enable_slow_query_logging(cls, threshold_ms: int = 100) -> None:
        """Enable slow query logging with specified threshold"""
        cls._slow_query_threshold_ms = threshold_ms
        cls._enabled = True
        logger.info(f"Slow query logging enabled (threshold: {threshold_ms}ms)")
    
    @classmethod
    def disable(cls) -> None:
        """Disable query monitoring"""
        cls._enabled = False
    
    @classmethod
    def record_query(cls, query: str, params: Any, duration_ms: float) -> None:
        """Record a query execution"""
        if not cls._enabled:
            return
        
        # Normalize query for pattern matching
        pattern = cls._normalize_query(query)
        
        # Update statistics
        if pattern not in cls._query_stats:
            cls._query_stats[pattern] = QueryStats(query_pattern=pattern)
        cls._query_stats[pattern].add_execution(duration_ms)
        
        # Check for slow query
        if duration_ms >= cls._slow_query_threshold_ms:
            cls._log_slow_query(query, params, duration_ms)
        
        # N+1 detection
        cls._check_n_plus_one(pattern)
        
        # Keep recent queries for analysis (max 1000)
        cls._recent_queries.append({
            "query": query[:500],
            "duration_ms": duration_ms,
            "timestamp": datetime.utcnow()
        })
        if len(cls._recent_queries) > 1000:
            cls._recent_queries = cls._recent_queries[-500:]
    
    @classmethod
    def _normalize_query(cls, query: str) -> str:
        """Normalize query for pattern matching (remove specific values)"""
        import re
        # Remove specific values
        normalized = re.sub(r"'[^']*'", "'?'", query)
        normalized = re.sub(r"\b\d+\b", "?", normalized)
        # Normalize whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized[:200]  # Limit pattern length
    
    @classmethod
    def _log_slow_query(cls, query: str, params: Any, duration_ms: float) -> None:
        """Log a slow query"""
        logger.warning(
            f"SLOW QUERY ({duration_ms:.2f}ms): {query[:300]}",
            extra={
                "query": query[:500],
                "params": str(params)[:200] if params else None,
                "duration_ms": duration_ms
            }
        )
    
    @classmethod
    def _check_n_plus_one(cls, pattern: str) -> None:
        """Detect potential N+1 query patterns"""
        now = datetime.utcnow()
        window = timedelta(seconds=1)
        
        # Add current execution
        cls._n_plus_one_detection[pattern].append(now)
        
        # Clean old entries
        cls._n_plus_one_detection[pattern] = [
            t for t in cls._n_plus_one_detection[pattern]
            if now - t < window
        ]
        
        # Check for N+1 pattern (same query executed many times in short window)
        count = len(cls._n_plus_one_detection[pattern])
        if count >= 10:  # Threshold for N+1 detection
            logger.warning(
                f"Potential N+1 query detected: {count} executions in 1 second",
                extra={"pattern": pattern, "count": count}
            )
    
    @classmethod
    def get_slow_queries(cls, limit: int = 20) -> List[Dict[str, Any]]:
        """Get top slow queries by average time"""
        sorted_stats = sorted(
            cls._query_stats.values(),
            key=lambda s: s.avg_time_ms,
            reverse=True
        )[:limit]
        
        return [
            {
                "pattern": s.query_pattern,
                "count": s.count,
                "avg_ms": round(s.avg_time_ms, 2),
                "max_ms": round(s.max_time_ms, 2),
                "total_ms": round(s.total_time_ms, 2)
            }
            for s in sorted_stats
        ]
    
    @classmethod
    def get_stats_summary(cls) -> Dict[str, Any]:
        """Get query statistics summary"""
        if not cls._query_stats:
            return {"message": "No queries recorded"}
        
        all_stats = list(cls._query_stats.values())
        total_queries = sum(s.count for s in all_stats)
        total_time = sum(s.total_time_ms for s in all_stats)
        
        return {
            "total_queries": total_queries,
            "unique_patterns": len(all_stats),
            "total_time_ms": round(total_time, 2),
            "avg_time_ms": round(total_time / total_queries, 2) if total_queries else 0,
            "slowest_query": max(all_stats, key=lambda s: s.max_time_ms).query_pattern if all_stats else None,
            "most_frequent": max(all_stats, key=lambda s: s.count).query_pattern if all_stats else None
        }
    
    @classmethod
    def reset_stats(cls) -> None:
        """Reset all statistics"""
        cls._query_stats = {}
        cls._recent_queries = []
        cls._n_plus_one_detection = defaultdict(list)


def setup_query_monitoring(engine: Engine) -> None:
    """
    Set up SQLAlchemy query monitoring.
    
    Call this after creating the engine:
        setup_query_monitoring(engine)
    """
    
    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault('query_start_time', []).append(time.time())
    
    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        start_times = conn.info.get('query_start_time', [])
        if start_times:
            start_time = start_times.pop()
            duration_ms = (time.time() - start_time) * 1000
            QueryOptimizer.record_query(statement, parameters, duration_ms)
    
    logger.info("Query monitoring set up successfully")


# === Index Recommendations ===

# Common indexes that should exist for clinic management
RECOMMENDED_INDEXES = [
    # Patients
    {"table": "patients", "columns": ["phone"], "name": "ix_patients_phone"},
    {"table": "patients", "columns": ["user_id"], "name": "ix_patients_user_id"},
    
    # Appointments
    {"table": "appointments", "columns": ["patient_id", "date"], "name": "ix_appointments_patient_date"},
    {"table": "appointments", "columns": ["doctor_id", "date"], "name": "ix_appointments_doctor_date"},
    {"table": "appointments", "columns": ["status"], "name": "ix_appointments_status"},
    
    # Visits
    {"table": "visits", "columns": ["patient_id", "created_at"], "name": "ix_visits_patient_created"},
    {"table": "visits", "columns": ["doctor_id", "created_at"], "name": "ix_visits_doctor_created"},
    {"table": "visits", "columns": ["status"], "name": "ix_visits_status"},
    
    # Queue entries
    {"table": "queue_entries", "columns": ["queue_id", "status"], "name": "ix_queue_entries_queue_status"},
    {"table": "queue_entries", "columns": ["patient_id"], "name": "ix_queue_entries_patient"},
    
    # Daily queues
    {"table": "daily_queues", "columns": ["department_id", "date"], "name": "ix_daily_queues_dept_date"},
    
    # Payments
    {"table": "payments", "columns": ["visit_id"], "name": "ix_payments_visit"},
    {"table": "payments", "columns": ["status", "created_at"], "name": "ix_payments_status_created"},
    
    # Users
    {"table": "users", "columns": ["username"], "name": "ix_users_username"},
    {"table": "users", "columns": ["email"], "name": "ix_users_email"},
    
    # Messages
    {"table": "messages", "columns": ["sender_id", "recipient_id"], "name": "ix_messages_sender_recipient"},
    {"table": "messages", "columns": ["created_at"], "name": "ix_messages_created"},
]


def check_missing_indexes(engine: Engine) -> List[Dict[str, Any]]:
    """
    Check for missing recommended indexes.
    
    Returns list of missing indexes with CREATE INDEX statements.
    """
    from sqlalchemy import inspect
    
    inspector = inspect(engine)
    missing = []
    
    for rec in RECOMMENDED_INDEXES:
        table = rec["table"]
        columns = rec["columns"]
        name = rec["name"]
        
        try:
            existing_indexes = inspector.get_indexes(table)
            existing_names = {idx["name"] for idx in existing_indexes}
            
            if name not in existing_names:
                # Check if any index covers these columns
                columns_set = set(columns)
                covered = any(
                    set(idx.get("column_names", [])) == columns_set
                    for idx in existing_indexes
                )
                
                if not covered:
                    cols_str = ", ".join(columns)
                    missing.append({
                        "table": table,
                        "columns": columns,
                        "name": name,
                        "sql": f"CREATE INDEX {name} ON {table} ({cols_str})"
                    })
        except Exception as e:
            logger.warning(f"Could not check indexes for {table}: {e}")
    
    return missing


def generate_index_migration(missing_indexes: List[Dict[str, Any]]) -> str:
    """Generate Alembic migration for missing indexes"""
    if not missing_indexes:
        return "# No missing indexes"
    
    lines = [
        '"""Add missing indexes for query optimization',
        '',
        'Revision ID: auto_generated',
        'Revises: HEAD',
        'Create Date: auto',
        '"""',
        '',
        'from alembic import op',
        '',
        '',
        'def upgrade():',
    ]
    
    for idx in missing_indexes:
        lines.append(f"    op.create_index('{idx['name']}', '{idx['table']}', {idx['columns']})")
    
    lines.extend([
        '',
        '',
        'def downgrade():',
    ])
    
    for idx in missing_indexes:
        lines.append(f"    op.drop_index('{idx['name']}', table_name='{idx['table']}')")
    
    return '\n'.join(lines)


# === Query Helper Functions ===

def explain_query(session, query) -> str:
    """
    Get EXPLAIN output for a query.
    
    Usage:
        from app.core.query_optimizer import explain_query
        print(explain_query(db, "SELECT * FROM patients WHERE phone = '123'"))
    """
    try:
        result = session.execute(text(f"EXPLAIN QUERY PLAN {query}"))
        return "\n".join(str(row) for row in result)
    except Exception as e:
        return f"Error: {e}"


@contextmanager
def query_timer(description: str = "Query"):
    """
    Context manager to time a query or operation.
    
    Usage:
        with query_timer("Fetch patients"):
            patients = db.query(Patient).all()
    """
    start = time.time()
    yield
    duration = (time.time() - start) * 1000
    logger.info(f"{description}: {duration:.2f}ms")
