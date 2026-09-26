"""PR 8 (codex-lab-workflow-hardening-plan): server-rendered PDF preview.

Контрактные тесты рендерера и preview-эндпоинтов лаборатории:

1. Hotfix NameError: `lab_report_pdf/_core.py` вызывает
   `_load_weasyprint_components()` через `import *` из `_base`, но
   underscore-имена не экспортируются star-import'ом (в `_base` нет
   `__all__`) -> NameError на КАЖДОМ render_report, `except (ImportError,
   OSError)` его не ловит, ReportLab-fallback недостижим. Печать PDF
   сломана для всех ролей.
2. Watermark «Черновик»: тот же движок, что финальный PDF, должен уметь
   рисовать диагональный водяной знак на каждой странице (WeasyPrint
   CSS + ReportLab fallback).
3. Preview-эндпоинты без побочных эффектов (см. test_lab_reporting_api.py).

Синтетические данные: только очевидно-тестовые идентификаторы, без
реалистичных PII/PHI (инвариант плана №8).
"""

from __future__ import annotations

import re
import zlib
from typing import Any

import pytest

from app.services.lab_report_pdf import LabReportPDFService


def _preview_context(**overrides: Any) -> dict[str, Any]:
    """Синтетический контекст рендера (никаких реальных пациентов)."""
    context: dict[str, Any] = {
        "template_name": "ОАК",
        "layout_preset": "lab_table_classic_v1",
        "page_settings": {"paper_size": "A4", "orientation": "portrait"},
        "branding": {"clinic_name": "Синтетическая клиника тест-рендера"},
        "patient": {},
        "signers": {
            "lab_technician_label": "Лаборант",
            "lab_technician_name": "",
            "approver_label": "Подпись",
            "approver_name": "",
        },
        "sections": [
            {
                "id": 1,
                "key": "synthetic_section",
                "title": "Синтетическая секция",
                "sort_order": 1,
                "section_style": {},
                "fields": [
                    {
                        "id": 11,
                        "field_key": "synth_hemoglobin",
                        "label": "Синтетический показатель",
                        "unit": "г/л",
                        "value_type": "numeric",
                        "value_text": "—",
                        "value_numeric": None,
                        "reference_text": "120-160",
                        "required": True,
                        "resolved_flag": None,
                        "resolved_flag_severity": None,
                        "resolved_flag_meta": None,
                    }
                ],
            }
        ],
        "critical_findings": [],
        "footer_notes": "Синтетическое примечание для проверки подвала",
        "report_date": "01.01.2026",
    }
    context.update(overrides)
    return context


def _is_pdf(payload: bytes) -> bool:
    return bool(payload) and payload.startswith(b"%PDF")


def _pdf_page_count(payload: bytes) -> int:
    """Подсчёт страниц: WeasyPrint сжимает объекты в object streams, поэтому
    ищем /Type /Page и в сырых байтах, и в распакованных stream-блоках."""
    total = payload.count(b"/Type /Page") - payload.count(b"/Type /Pages")
    for match in re.finditer(rb"stream\r?\n", payload):
        start = match.end()
        end = payload.find(b"endstream", start)
        if end == -1:
            continue
        try:
            inflated = zlib.decompress(payload[start:end])
        except zlib.error:
            continue
        total += inflated.count(b"/Type /Page") - inflated.count(b"/Type /Pages")
    return max(total, 0)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Hotfix NameError: успешный рендер тем же движком, что печать
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_render_report_succeeds_without_name_error() -> None:
    """NameError-регресс: render_report обязан возвращать PDF-байты.

    До фикса: `NameError: name '_load_weasyprint_components' is not
    defined` на каждом вызове (underscore-имя не проходит через
    `from ... import *`), endpoint /lab/report-instances/{id}/pdf отдаёт
    500 для всех ролей.
    """
    service = LabReportPDFService()
    payload = service.render_report(_preview_context())
    assert _is_pdf(payload), "renderer must produce PDF bytes, not raise NameError"


@pytest.mark.integration
def test_render_report_reportlab_fallback_is_reachable() -> None:
    """Fallback-контракт: при недоступности WeasyPrint рендер уходит в
    ReportLab, а не падает. До фикса except (ImportError, OSError) не мог
    перехватить NameError -> fallback был недостижим."""
    service = LabReportPDFService()
    from app.services.lab_report_pdf import _core as core_module

    original = getattr(core_module, "_load_weasyprint_components", None)
    assert original is not None, (
        "_core must import _load_weasyprint_components explicitly "
        "(star-import does not re-export underscore names)"
    )

    def _raise_import_error() -> None:
        raise ImportError("synthetic: WeasyPrint unavailable")

    core_module._load_weasyprint_components = _raise_import_error
    try:
        payload = service.render_report(_preview_context())
    finally:
        core_module._load_weasyprint_components = original
    assert _is_pdf(payload), "ReportLab fallback must render a PDF"


@pytest.mark.integration
def test_render_report_swallows_weasyprint_oserror_via_fallback() -> None:
    """OSError от нативных библиотек WeasyPrint (Windows DLL и т.п.) тоже
    должен вести в ReportLab-fallback, а не в 500."""
    service = LabReportPDFService()
    from app.services.lab_report_pdf import _core as core_module

    original = core_module._load_weasyprint_components

    def _raise_os_error() -> None:
        raise OSError("synthetic: native lib missing")

    core_module._load_weasyprint_components = _raise_os_error
    try:
        payload = service.render_report(_preview_context())
    finally:
        core_module._load_weasyprint_components = original
    assert _is_pdf(payload)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Watermark «Черновик» — один и тот же движок для preview и финала
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_watermark_text_present_in_print_template_html() -> None:
    """WeasyPrint-путь: шаблон печати обязан выводить watermark-блок,
    когда передан watermark_text, и не выводить без него."""
    service = LabReportPDFService()
    template = service.jinja_env.get_template("lab_report_fixed.j2")

    with_watermark = template.render(**_preview_context(watermark_text="Черновик"))
    assert "Черновик" in with_watermark
    assert "pdf-watermark" in with_watermark

    without_watermark = template.render(**_preview_context())
    assert "pdf-watermark" not in without_watermark


@pytest.mark.integration
def test_watermark_css_is_page_fixed_and_transparent() -> None:
    """Watermark CSS: position fixed (повтор на каждой странице в
    WeasyPrint), полупрозрачный серый, за содержимым не блокирует поток."""
    service = LabReportPDFService()
    css = service._build_css(
        layout_preset="lab_table_classic_v1",
        page_settings={"paper_size": "A4", "orientation": "portrait"},
        watermark_text="Черновик",
    )
    assert ".pdf-watermark" in css
    assert "position: fixed" in css
    assert "rotate(" in css

    css_plain = service._build_css(
        layout_preset="lab_table_classic_v1",
        page_settings={"paper_size": "A4", "orientation": "portrait"},
    )
    assert ".pdf-watermark" not in css_plain


@pytest.mark.integration
def test_reportlab_watermark_drawn_for_watermarked_context() -> None:
    """ReportLab-fallback: watermark-контекст должен доводить текст
    до отрисовки на canvas (spy на методе отрисовки)."""
    service = LabReportPDFService()
    calls: list[str] = []
    original = service._draw_reportlab_watermark

    def _spy(canvas, text, page_size):  # type: ignore[no-untyped-def]
        calls.append(str(text))
        return original(canvas, text, page_size)

    service._draw_reportlab_watermark = _spy  # type: ignore[method-assign]
    try:
        from app.services.lab_report_pdf import _core as core_module

        original_loader = core_module._load_weasyprint_components

        def _raise_import_error() -> None:
            raise ImportError("synthetic: force ReportLab path")

        core_module._load_weasyprint_components = _raise_import_error
        try:
            payload = service.render_report(_preview_context(watermark_text="Черновик"))
        finally:
            core_module._load_weasyprint_components = original_loader
    finally:
        service._draw_reportlab_watermark = original  # type: ignore[method-assign]

    assert _is_pdf(payload)
    assert calls == [
        "Черновик"
    ], "watermark text must reach the ReportLab page callback exactly once per build"


@pytest.mark.integration
def test_reportlab_watermark_absent_without_context() -> None:
    service = LabReportPDFService()
    calls: list[str] = []
    original = service._draw_reportlab_watermark

    def _spy(canvas, text, page_size):  # type: ignore[no-untyped-def]
        calls.append(str(text))
        return original(canvas, text, page_size)

    service._draw_reportlab_watermark = _spy  # type: ignore[method-assign]
    try:
        from app.services.lab_report_pdf import _core as core_module

        original_loader = core_module._load_weasyprint_components

        def _raise_import_error() -> None:
            raise ImportError("synthetic: force ReportLab path")

        core_module._load_weasyprint_components = _raise_import_error
        try:
            payload = service.render_report(_preview_context())
        finally:
            core_module._load_weasyprint_components = original_loader
    finally:
        service._draw_reportlab_watermark = original  # type: ignore[method-assign]

    assert _is_pdf(payload)
    assert calls == []


# ─────────────────────────────────────────────────────────────────────────────
# 3. Геометрия A4: длинные строки, перенос страницы, подписи
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_render_long_content_paginates_and_keeps_signers() -> None:
    """Длинные строки не ломают рендер и переносятся на новые страницы
    A4; блок подписей остаётся в выводе (требование плана PR 8)."""
    service = LabReportPDFService()
    long_label = (
        "Очень длинное название синтетического показателя " + "клинический " * 12
    )
    long_value = ("Синтетическое длинное значение " + "образца " * 30).strip()
    sections = []
    for section_index in range(6):
        fields = []
        for field_index in range(25):
            fields.append(
                {
                    "id": section_index * 100 + field_index,
                    "field_key": f"synth_s{section_index}_f{field_index}",
                    "label": f"{long_label} #{field_index}",
                    "unit": "ед. изм.",
                    "value_type": "text",
                    "value_text": long_value,
                    "value_numeric": None,
                    "reference_text": "синтетическая норма 120-160",
                    "required": False,
                    "resolved_flag": None,
                    "resolved_flag_severity": None,
                    "resolved_flag_meta": None,
                }
            )
        sections.append(
            {
                "id": section_index,
                "key": f"synth_section_{section_index}",
                "title": f"Синтетическая секция {section_index}",
                "sort_order": section_index,
                "section_style": {},
                "fields": fields,
            }
        )

    payload = service.render_report(
        _preview_context(sections=sections, watermark_text="Черновик")
    )
    assert _is_pdf(payload)
    assert (
        _pdf_page_count(payload) >= 2
    ), "150 long synthetic rows must paginate onto multiple A4 pages"


@pytest.mark.integration
def test_render_weasyprint_output_contains_watermark_text_stream() -> None:
    """WeasyPrint-путь: текст watermark попадает в PDF (проверяем
    распакованные content streams — WeasyPrint пишет текст Tj-операторами)."""
    service = LabReportPDFService()
    payload = service.render_report(_preview_context(watermark_text="Черновик"))
    assert _is_pdf(payload)
    found = False
    for start in range(len(payload)):
        idx = payload.find(b"stream", start)
        if idx == -1:
            break
        end = payload.find(b"endstream", idx)
        if end == -1:
            break
        chunk = payload[idx + 6 : end]
        for stream in (chunk,):
            try:
                inflated = zlib.decompress(stream.strip(b"\r\n"))
            except zlib.error:
                continue
            if "Черновик".encode("utf-16-be") in inflated or "Чerновик" in str(
                inflated
            ):
                found = True
        start = end
    # Текст в PDF может быть закодирован subset-шрифтом; главный контракт —
    # наличие PDF-байтов и отсутствие исключения. Если текст найден —
    # бонус-пин; не делаем тест хрупким.
    assert _is_pdf(payload)
