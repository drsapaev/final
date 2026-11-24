"""Preserve lexical JSON amounts and validate exact database money values.

``parse_exact_json`` must run on the original request body: no helper can
recover decimal digits already rounded by a float JSON parser. Authorization
and the choice of which request fields represent money belong to callers.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any


class MoneyInputError(ValueError):
    """An untrusted JSON payload or monetary value cannot be represented."""


MAX_MONEY = Decimal("9999999999.99")  # PostgreSQL Numeric(12, 2)
_MONEY_UNIT = Decimal("0.01")
_NUMBER_TEXT = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$")


def parse_exact_json(raw: str | bytes | bytearray) -> Any:
    """Decode JSON without binary-float rounding and retain last duplicate key.

    ``json.loads`` provides the same last-key-wins semantics as Starlette's
    default decoder; ``Decimal`` also preserves nonfinite constants for the
    caller's field validation rather than silently coercing them to zero.
    """
    try:
        return json.loads(raw, parse_float=Decimal, parse_constant=Decimal)
    except (ValueError, TypeError, UnicodeError, OverflowError, RecursionError, InvalidOperation):
        # Parser exceptions can contain a supplied document: never expose them.
        raise MoneyInputError("Некорректный JSON") from None


def parse_money(value: object) -> Decimal:
    """Return an exactly representable, nonnegative Numeric(12, 2) amount.

    Values with insignificant trailing zeros are accepted. Floats passed by
    internal callers are interpreted using their shortest decimal spelling;
    HTTP callers needing lexical precision must use ``parse_exact_json``.
    """
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, float, str)):
        raise MoneyInputError("Некорректная денежная сумма")
    if isinstance(value, str):
        value = value.strip()
        if not _NUMBER_TEXT.fullmatch(value):
            raise MoneyInputError("Некорректная денежная сумма")
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > MAX_MONEY:
            raise MoneyInputError("Некорректная денежная сумма")
        # Numeric(12,2) requires at most 12 significant digits. A local
        # precision makes validation independent of an ambient caller context.
        with localcontext() as context:
            context.prec = max(context.prec, 20)
            normalized = amount.quantize(_MONEY_UNIT)
        if normalized != amount:
            raise MoneyInputError("Некорректная денежная сумма")
        return Decimal("0.00") if not normalized else normalized
    except (InvalidOperation, TypeError, ValueError, OverflowError):
        raise MoneyInputError("Некорректная денежная сумма") from None
