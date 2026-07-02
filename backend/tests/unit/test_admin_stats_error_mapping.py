from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.admin_stats import (
    get_activity_chart,
    get_admin_stats,
    get_analytics_charts,
    get_analytics_overview,
    get_quick_stats,
)


class _BrokenDb:
    def query(self, *args, **kwargs):
        raise RuntimeError("sensitive internal diagnostic")


@pytest.mark.parametrize(
    "call_endpoint",
    [
        lambda db: get_admin_stats(db=db, _=object()),
        lambda db: get_quick_stats(db=db, _=object()),
        lambda db: get_activity_chart(days=1, db=db, _=object()),
        lambda db: get_analytics_overview(
            period="week",
            department=None,
            doctor_id=None,
            db=db,
            _=object(),
        ),
        lambda db: get_analytics_charts(
            period="week",
            chart_type="appointments",
            department=None,
            db=db,
            _=object(),
        ),
    ],
)
def test_admin_stats_500_errors_do_not_expose_exception_text(
    call_endpoint: Callable[[_BrokenDb], object],
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        call_endpoint(_BrokenDb())

    assert exc_info.value.status_code == 500
    assert "sensitive internal diagnostic" not in str(exc_info.value.detail)
