"""Build the same report-version context for preview, print, and delivery."""

from datetime import UTC, datetime

from app.models.lab import FINAL_INSTANCE_STATUSES


def build_report_pdf_context(service, instance, *, preview: bool = False) -> dict:
    finalized = instance.status in FINAL_INSTANCE_STATUSES
    signed_on = instance.finalized_at or instance.created_at or datetime.now(UTC)
    sections = service.materialize_instance(instance)
    replacement_id = getattr(instance, "supersedes_instance_id", None)
    version_number = getattr(instance.template_version, "version_no", None)
    document = f"Отчёт №{instance.id}"
    if version_number is not None:
        document += f" · Шаблон v{version_number}"
    if replacement_id is not None:
        document += f" · Исправление к отчёту №{replacement_id}"
    context = {
        "template_name": instance.template.name,
        "layout_preset": instance.template_version.layout_preset,
        "page_settings": instance.template_version.page_settings or {},
        "branding": instance.branding_snapshot or {},
        "patient": instance.patient_snapshot or {},
        "signers": instance.signer_snapshot or {},
        "sections": sections,
        "critical_findings": service.summarize_critical_findings(sections),
        "footer_notes": instance.template_version.footer_notes,
        "report_date": signed_on.strftime("%d.%m.%Y"),
        "report_document_label": document,
        "report_release_label": (
            f"Выпущен {instance.finalized_at.isoformat(timespec='minutes')}"
            if instance.finalized_at is not None
            else None
        ),
    }
    if (
        replacement_id is not None
        and getattr(instance, "managed_release", False) is True
    ):
        correction = service._latest_workflow_event(instance.id, "revision_created")
        if correction is not None and correction.reason:
            context["report_correction_reason"] = (
                f"Причина исправления · {correction.reason}"
            )
    if preview:
        context["watermark_text"] = None if finalized else "Черновик"
    return context
