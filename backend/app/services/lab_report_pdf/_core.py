"""Core mixin for LabReportPDFService.

Split from lab_report_pdf_service.py.
"""
from __future__ import annotations

from app.services.lab_report_pdf._base import *  # noqa: F401, F403
from app.services.lab_report_pdf._base import LabReportPDFServiceMixinBase


class CoreMixin(LabReportPDFServiceMixinBase):
    """Core methods."""

    def __init__(self) -> None:
        self.backend_root = Path(__file__).resolve().parents[2]
        self.templates_dir = self.backend_root / "app" / "templates" / "print"
        self.jinja_env = Environment(autoescape=True,
            loader=FileSystemLoader(self.templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )


    def render_report(self, context: dict[str, Any]) -> bytes:
        layout_preset = context.get("layout_preset") or "lab_table_classic_v1"
        page_settings = context.get("page_settings") or {}
        context = dict(context)
        context["generated_at"] = datetime.now(UTC)
        context["oam_docx_mode"] = self._is_oam_docx_template(context)
        context["smear_matrix_mode"] = self._is_smear_matrix_template(context)
        context["docx_three_column_mode"] = self._is_docx_three_column_template(context)
        context["copy_count"] = self._resolve_copy_count(context)
        context["branding"] = dict(context.get("branding") or {})
        context["branding"]["logo_file_url"] = self._resolve_logo_url(
            context["branding"].get("logo_url")
        )
        logger.info(
            "[LAB][PDF] render_report layout_preset=%s page_settings=%s",
            layout_preset,
            page_settings,
        )
        try:
            weasy_css, weasy_html = _load_weasyprint_components()
        except (ImportError, OSError) as exc:
            if REPORTLAB_AVAILABLE:
                logger.warning("[LAB][PDF] falling back to ReportLab renderer: %s", exc)
                return self._render_reportlab(context)
            raise

        template = self.jinja_env.get_template("lab_report_fixed.j2")
        html_content = template.render(**context)
        css_content = self._build_css(layout_preset=layout_preset, page_settings=page_settings)
        html_doc = weasy_html(string=html_content, base_url=str(self.backend_root))
        css_doc = weasy_css(string=css_content)
        return html_doc.write_pdf(stylesheets=[css_doc])


    def _resolve_copy_count(self, context: dict[str, Any]) -> int:
        if self._is_docx_three_column_template(context):
            return 1
        if self._is_smear_matrix_template(context):
            return 2
        sections = context.get("sections") or []
        for section in sections:
            section_style = section.get("section_style") or {}
            copy_count = section_style.get("copy_count")
            if copy_count is not None:
                try:
                    value = int(copy_count)
                    if value > 0:
                        return value
                except (TypeError, ValueError):
                    continue
        return 1


    def _is_smear_matrix_template(self, context: dict[str, Any]) -> bool:
        if str(context.get("template_name") or "").strip() == "Мазок":
            return True
        for section in context.get("sections") or []:
            section_style = section.get("section_style") or {}
            if str(section_style.get("render") or "").strip() == "smear_matrix":
                return True
        return False


    def _is_oam_docx_template(self, context: dict[str, Any]) -> bool:
        if str(context.get("template_name") or "").strip() == "ОАМ":
            return True
        for section in context.get("sections") or []:
            section_style = section.get("section_style") or {}
            if str(section_style.get("render") or "").strip() == "oam_docx":
                return True
        return False


    def _is_docx_three_column_template(self, context: dict[str, Any]) -> bool:
        template_name = str(context.get("template_name") or "").strip()
        if template_name in {"ОАК", "Биохимия"}:
            return True
        for section in context.get("sections") or []:
            section_style = section.get("section_style") or {}
            if str(section_style.get("render") or "").strip() == "docx_three_column":
                return True
        return False


