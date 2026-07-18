"""print_svc — split from print_service.py.

Re-exports PrintService for backward compatibility.
"""
from __future__ import annotations

from app.services.print_svc._base import *  # noqa: F401, F403
from app.services.print_svc._base import PrintServiceMixinBase
from app.services.print_svc._core import CoreMixin
from app.services.print_svc._helpers import HelpersMixin
from app.services.print_svc._rendering import RenderingMixin

__all__ = ["PrintService"]


class PrintService(
    CoreMixin,
    RenderingMixin,
    HelpersMixin,
    PrintServiceMixinBase,
):
    """Composed of focused mixin modules."""

    def __init__(self, db: Session):
        self.db = db
        self.templates_dir = Path(__file__).parent.parent / "templates" / "print"

        # Настройка Jinja2
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Добавляем фильтры
        self.jinja_env.filters['strftime'] = self._strftime_filter
        self.jinja_env.filters['number_format'] = self._number_format_filter
        self.jinja_env.filters['nl2br'] = self._nl2br_filter
