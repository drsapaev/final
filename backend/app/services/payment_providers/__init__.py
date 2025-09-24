"""
Провайдеры платежных систем для клиники
"""
from .base import BasePaymentProvider
from .click import ClickProvider
from .payme import PayMeProvider
from .kaspi import KaspiProvider

__all__ = [
    "BasePaymentProvider",
    "ClickProvider", 
    "PayMeProvider",
    "KaspiProvider"
]
