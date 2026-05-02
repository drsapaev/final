"""
Простые тесты для проверки покрытия кода
"""
import pytest


def test_simple_math():
    """Простой тест для проверки работы pytest"""
    assert 2 + 2 == 4
    assert 5 * 3 == 15


def test_string_operations():
    """Тест строковых операций"""
    text = "Hello World"
    assert text.lower() == "hello world"
    assert text.upper() == "HELLO WORLD"
    assert len(text) == 11


def test_list_operations():
    """Тест операций со списками"""
    numbers = [1, 2, 3, 4, 5]
    assert len(numbers) == 5
    assert sum(numbers) == 15
    assert max(numbers) == 5
    assert min(numbers) == 1


def test_dict_operations():
    """Тест операций со словарями"""
    data = {"name": "Test", "value": 42}
    assert data["name"] == "Test"
    assert data["value"] == 42
    assert len(data) == 2
