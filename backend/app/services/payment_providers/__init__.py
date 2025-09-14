"""
Провайдеры платежных систем для клиники
"""
from .base import BasePaymentProvider
from .click import ClickProvider
from .payme import PaymeProvider
from .kaspi import KaspiProvider

__all__ = [
    "BasePaymentProvider",
    "ClickProvider", 
    "PaymeProvider",
    "KaspiProvider"
]
