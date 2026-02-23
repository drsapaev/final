"""
Monitoring API endpoints for system diagnostics.

Provides endpoints for:
- Query performance statistics
- Alert history
- System health details
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_active_user, require_roles

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/query-stats", dependencies=[Depends(require_roles(["Admin"]))])
def get_query_stats():
    """
    Get database query statistics.
    Only available in dev/staging environments.
    """
    try:
        from app.core.query_optimizer import QueryOptimizer
        return {
            "summary": QueryOptimizer.get_stats_summary(),
            "slow_queries": QueryOptimizer.get_slow_queries(limit=20)
        }
    except ImportError:
        return {"error": "Query monitoring not available"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/alerts", dependencies=[Depends(require_roles(["Admin"]))])
def get_alerts(hours: int = 24):
    """
    Get recent alerts.
    
    Args:
        hours: Number of hours to look back (default 24)
    """
    try:
        from app.core.alerts import alert_manager
        
        alerts = alert_manager.get_recent_alerts(hours=hours)
        return {
            "count": len(alerts),
            "alerts": [
                {
                    "type": a.alert_type.value,
                    "severity": a.severity.value,
                    "message": a.message,
                    "timestamp": a.timestamp.isoformat(),
                    "resolved": a.resolved,
                    "details": a.details
                }
                for a in alerts
            ],
            "stats": alert_manager.get_alert_stats()
        }
    except ImportError:
        return {"error": "Alert system not available"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/missing-indexes", dependencies=[Depends(require_roles(["Admin"]))])
def get_missing_indexes():
    """
    Check for missing recommended database indexes.
    """
    try:
        from app.core.query_optimizer import check_missing_indexes, generate_index_migration
        from app.db.session import engine
        
        missing = check_missing_indexes(engine)
        return {
            "missing_count": len(missing),
            "missing_indexes": missing,
            "migration_script": generate_index_migration(missing) if missing else None
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/reset-query-stats", dependencies=[Depends(require_roles(["Admin"]))])
def reset_query_stats():
    """Reset query statistics"""
    try:
        from app.core.query_optimizer import QueryOptimizer
        QueryOptimizer.reset_stats()
        return {"status": "ok", "message": "Query statistics reset"}
    except ImportError:
        return {"error": "Query monitoring not available"}
