"""
Провайдеры платежных систем для клиники
"""

from .base import BasePaymentProvider
from .click import ClickProvider
from .kaspi import KaspiProvider
from .payme import PayMeProvider

__all__ = ["BasePaymentProvider", "ClickProvider", "PayMeProvider", "KaspiProvider"]
