#!/usr/bin/env python3
"""
Unit tests for print_templates.py SSTI hardening.

Closes CodeQL regressions for:
  - py/template-injection #1170, #1171

These tests verify that the SandboxedEnvironment blocks known SSTI payloads.
A regular jinja2.Environment with autoescape=True would let these payloads
traverse Python's class hierarchy to escape the sandbox; SandboxedEnvironment
raises SecurityError instead.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from jinja2.exceptions import SecurityError, TemplateError

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.v1.endpoints.print_templates import _make_template_env  # noqa: E402


# ============================================================
# SSTI payloads — all should be blocked by SandboxedEnvironment
# Reference: https://github.com/swisskyrepo/PayloadsAllTheThings/tree/master/SSTI
# ============================================================

SSTI_PAYLOADS = [
    # Class hierarchy traversal — the classic SSTI escape
    "{{ ''.__class__.__mro__[1].__subclasses__() }}",
    "{{ ''.__class__.__mro__[2].__subclasses__() }}",
    "{{ ().__class__.__bases__[0].__subclasses__() }}",
    "{{ ().__class__.__mro__[1].__subclasses__() }}",
    "{{ request.__class__.__mro__ }}",
    # __import__ / builtins access
    "{{ cycler.__init__.__globals__.os }}",
    "{{ joiner.__init__.__globals__.os }}",
    "{{ namespace.__init__.__globals__.os }}",
    # getitem trick to bypass naive attr filters
    "{{ ''['__class__']['__mro__'][1]['__subclasses__']() }}",
    # attr filter bypass
    "{{ ''|attr('__class__') }}",
    "{{ ''|attr('__class__')|attr('__mro__') }}",
    "{{ ''|attr('__class__')|attr('__mro__')|attr('__getitem__')(1) }}",
    # Popen via subprocess
    "{{ ''.__class__.__mro__[1].__subclasses__()[XXX]('id',shell=True,stdout=-1).communicate() }}",
    # Lipsum trick
    "{{ lipsum.__globals__ }}",
    "{{ lipsum.__globals__['os'].popen('id').read() }}",
]


class TestSSTIBlocked:
    """Verify that SandboxedEnvironment blocks known SSTI payloads."""

    @pytest.mark.parametrize("payload", SSTI_PAYLOADS)
    def test_ssti_payload_blocked(self, payload: str) -> None:
        env = _make_template_env()
        # Some payloads raise at parse time (from_string); others at render time.
        # Both are acceptable — the key is that NO payload successfully executes.
        try:
            template = env.from_string(payload)
        except (SecurityError, TemplateError):
            return  # blocked at parse time — good

        # If parse succeeded, render must raise SecurityError or fail safely.
        try:
            result = template.render()
        except (SecurityError, TemplateError):
            return  # blocked at render time — good

        # If we got here, the payload rendered without error. Verify it did NOT
        # produce evidence of successful SSTI (subprocess output, class list, etc.).
        forbidden = [
            "<class 'subprocess.Popen'>",
            "<class 'os.",
            "ProcessLookupError",
            "<built-in function",
            "__globals__",
            "/etc/passwd",
            "uid=",
        ]
        for token in forbidden:
            assert token not in result, (
                f"SSTI payload succeeded: {payload!r} produced output containing {token!r}: {result!r}"
            )


# ============================================================
# Legitimate templates still render correctly
# ============================================================

class TestLegitimateTemplates:
    """Verify that legitimate Jinja2 templates still render correctly."""

    def test_simple_variable(self) -> None:
        env = _make_template_env()
        template = env.from_string("Hello, {{ name }}!")
        assert template.render(name="World") == "Hello, World!"

    def test_conditional(self) -> None:
        env = _make_template_env()
        template = env.from_string(
            "{% if patient_name %}Patient: {{ patient_name }}{% else %}No patient{% endif %}"
        )
        assert template.render(patient_name="Ivan") == "Patient: Ivan"
        assert template.render() == "No patient"

    def test_loop(self) -> None:
        env = _make_template_env()
        template = env.from_string(
            "{% for item in items %}{{ item }},{% endfor %}"
        )
        assert template.render(items=["a", "b", "c"]) == "a,b,c,"

    def test_autoescape_html(self) -> None:
        """autoescape=True must HTML-escape by default."""
        env = _make_template_env()
        template = env.from_string("{{ user_input }}")
        result = template.render(user_input="<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_date_formatting(self) -> None:
        """Common use case: formatting dates in print templates."""
        env = _make_template_env()
        template = env.from_string("{{ date.strftime('%Y-%m-%d') }}")
        from datetime import datetime
        result = template.render(date=datetime(2026, 1, 15))
        assert result == "2026-01-15"

    def test_attribute_access_on_dict(self) -> None:
        """SandboxedEnvironment allows attribute access on user-provided objects
        but blocks dunder access. Verify dict.attr syntax works for normal attrs."""
        env = _make_template_env()
        template = env.from_string("{{ obj.name }} - {{ obj.age }}")

        class Person:
            def __init__(self, name: str, age: int) -> None:
                self.name = name
                self.age = age

        result = template.render(obj=Person("Ivan", 42))
        assert result == "Ivan - 42"

    def test_no_dunder_access_on_user_objects(self) -> None:
        """SandboxedEnvironment blocks dunder attribute access on user objects.

        Behavior: single-level dunder access returns Undefined (renders as '');
        chained dunder access raises SecurityError. Both outcomes block SSTI.
        """
        env = _make_template_env()

        class Person:
            pass

        # Single-level: silently undefined (renders as empty string)
        template = env.from_string("{{ obj.__class__ }}")
        result = template.render(obj=Person())
        assert result == "", f"Expected empty (Undefined), got: {result!r}"

        # Chained: raises SecurityError
        template2 = env.from_string("{{ obj.__class__.__mro__ }}")
        with pytest.raises(SecurityError):
            template2.render(obj=Person())


# ============================================================
# Autoescape behavior preserved
# ============================================================

class TestAutoescapePreserved:
    """Verify that autoescape=True (XSS protection) is still enabled."""

    def test_autoescape_on_by_default(self) -> None:
        env = _make_template_env()
        # SandboxedEnvironment should have autoescape=True set by us
        assert env.autoescape is True
