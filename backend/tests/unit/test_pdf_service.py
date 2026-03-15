from __future__ import annotations

import importlib

import pytest


def test_pdf_service_import_survives_missing_weasyprint_runtime():
    module = importlib.import_module("app.services.pdf_service")
    assert hasattr(module, "PDFService")


def test_generate_pdf_from_html_reports_weasyprint_runtime_issue(monkeypatch):
    module = importlib.import_module("app.services.pdf_service")
    service = module.PDFService()

    def _raise_runtime_issue():
        raise OSError("libgobject-2.0-0 missing")

    monkeypatch.setattr(module, "_load_weasyprint_components", _raise_runtime_issue)

    with pytest.raises(Exception, match="WeasyPrint недоступен"):
        service.generate_pdf_from_html("unused.html", {}, "A4")
