"""Exact untrusted money parsing without leaking request content."""
from __future__ import annotations

from decimal import Decimal, localcontext

import pytest

from app.services.money_input import (
    MAX_MONEY,
    MoneyInputError,
    parse_exact_json,
    parse_money,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, "0.00"),
        (-0.0, "0.00"),
        ("-0.000", "0.00"),
        (".5", "0.50"),
        (" 123.4500 ", "123.45"),
        (Decimal("123.45"), "123.45"),
        (123.45, "123.45"),
        ("1e3", "1000.00"),
        ("9999999999.99", "9999999999.99"),
    ],
)
def test_valid_values_have_exact_cents(value, expected):
    result = parse_money(value)
    assert result == Decimal(expected)
    assert result.as_tuple().exponent == -2


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        None,
        [],
        {},
        "",
        "1_0",
        "1,000.00",
        "-0.01",
        "0.001",
        "123.450000000000000001",
        "1e-1000",
        "10000000000.00",
        "1e999999999999999999999999999999",
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_unrepresentable_values_are_rejected_without_echoing_input(value):
    with pytest.raises(MoneyInputError) as exc:
        parse_money(value)
    assert str(exc.value) == "Некорректная денежная сумма"


@pytest.mark.parametrize(
    "raw_number,valid",
    [
        (b"0", True),
        (b"123.45", True),
        (b'"123.45"', True),
        (b"9999999999.99", True),
        (b"10000000000.00", False),
        (b"123.450000000000000001", False),
        (b"1e-1000", False),
        (b"NaN", False),
        (b"Infinity", False),
        (b"-Infinity", False),
    ],
)
def test_json_number_keeps_full_lexical_precision(raw_number, valid):
    value = parse_exact_json(b'{"amount":' + raw_number + b'}')["amount"]
    if valid:
        result = parse_money(value)
        assert Decimal("0.00") <= result <= MAX_MONEY
    else:
        with pytest.raises(MoneyInputError):
            parse_money(value)


@pytest.mark.parametrize(
    "body,expected",
    [
        (b'{"amount":0.001,"amount":123.45}', Decimal("123.45")),
        (b'{"amount":123.45,"amount":0.001}', None),
        (b'{"amount":NaN,"amount":"123.45"}', Decimal("123.45")),
        (b'{"amount":"123.45","amount":NaN}', None),
    ],
)
def test_duplicate_keys_follow_standard_last_key_wins(body, expected):
    amount = parse_exact_json(body)["amount"]
    if expected is None:
        with pytest.raises(MoneyInputError):
            parse_money(amount)
    else:
        assert parse_money(amount) == expected


@pytest.mark.parametrize("body", [b'{"amount":}', b'{"amount": 1', b"\xff", b"[]{}", "{private-information"])
def test_invalid_json_does_not_echo_raw_input(body):
    with pytest.raises(MoneyInputError) as exc:
        parse_exact_json(body)
    assert str(exc.value) == "Некорректный JSON"


def test_json_does_not_convert_unrelated_values_or_require_object():
    parsed = parse_exact_json(b'[true, null, 9, 1.25, "text"]')
    assert parsed == [True, None, 9, Decimal("1.25"), "text"]
    assert type(parsed[2]) is int
    assert type(parsed[3]) is Decimal


def test_valid_large_amount_is_independent_of_ambient_decimal_precision():
    with localcontext() as context:
        context.prec = 4
        assert parse_money("9999999999.99") == MAX_MONEY


def test_pathological_exponents_and_integer_size_never_become_zero_or_crash():
    for raw in (
        b'{"amount":1e999999999999999999999999999999}',
        b'{"amount":1e-999999999999999999999999999999}',
        b'{"amount":' + b"9" * 10000 + b'}',
    ):
        with pytest.raises(MoneyInputError):
            parse_money(parse_exact_json(raw)["amount"])
