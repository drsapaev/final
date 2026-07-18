"""Versions mixin for LabReportingService.

Split from lab_reporting_service.py.
"""
from __future__ import annotations

from app.services.lab_reporting._base import *  # noqa: F401, F403
from app.services.lab_reporting._base import LabReportingServiceMixinBase


class VersionsMixin(LabReportingServiceMixinBase):
    """Versions methods for LabReportingService."""

    def create_template_version(
        self, template_id: int, source_version_id: int | None = None
    ) -> LabReportTemplateVersion:
        logger.info(
            "[LAB] create_template_version template_id=%s source_version_id=%s",
            template_id,
            source_version_id,
        )
        template = self.get_template(template_id)
        source = (
            self.repository.get_template_version(source_version_id)
            if source_version_id
            else self.repository.get_latest_draft_version(template.id)
            or self.repository.get_latest_published_version(template.id)
            or self.repository.get_latest_version(template.id)
        )
        next_version = (
            self.repository.get_latest_version(template.id).version_no + 1
            if template.versions
            else 1
        )
        draft = LabReportTemplateVersion(
            template_id=template.id,
            version_no=next_version,
            status="DRAFT",
            layout_preset=source.layout_preset if source else "lab_table_classic_v1",
            page_settings=deepcopy(source.page_settings) if source else {"paper_size": "A4"},
            branding_overrides=deepcopy(source.branding_overrides) if source else {},
            signer_defaults=deepcopy(source.signer_defaults) if source else {},
            footer_notes=source.footer_notes if source else None,
            seed_signature=None,
        )
        self.repository.add_template_version(draft)
        if source:
            self._replace_version_sections(draft, self._sections_to_payload(source.sections))
        self.repository.commit()
        logger.info("[LAB] create_template_version created version_id=%s", draft.id)
        return self.repository.get_template_version(draft.id)


    def template_version_available_actions(
        self, version: LabReportTemplateVersion,
    ) -> list[str]:
        if version.status == "DRAFT":
            return ["update", "publish"]
        return ["create_draft"]


    def template_version_action_flags(
        self, version: LabReportTemplateVersion,
    ) -> dict[str, bool]:
        available_actions = set(self.template_version_available_actions(version))
        return {
            "can_update": "update" in available_actions,
            "can_publish": "publish" in available_actions,
            "can_create_draft": "create_draft" in available_actions,
        }


    def update_template_version(
        self, version_id: int, payload: dict[str, Any]
    ) -> LabReportTemplateVersion:
        logger.info("[LAB] update_template_version version_id=%s", version_id)
        self.ensure_default_catalog()
        self._validate_catalog_links(payload.get("sections") or [])
        version = self.repository.get_template_version(version_id)
        if not version:
            raise LabReportingDomainError(404, "Template version not found")
        if version.status != "DRAFT":
            raise LabReportingDomainError(409, "Only draft versions can be updated")

        version.layout_preset = payload["layout_preset"]
        version.page_settings = payload.get("page_settings") or {}
        version.branding_overrides = payload.get("branding_overrides") or {}
        version.signer_defaults = payload.get("signer_defaults") or {}
        version.footer_notes = payload.get("footer_notes")
        version.seed_signature = None
        self._replace_version_sections(version, payload.get("sections") or [])
        self.repository.commit()
        logger.info("[LAB] update_template_version saved version_id=%s", version.id)
        return self.repository.get_template_version(version.id)


    def publish_template_version(self, version_id: int) -> LabReportTemplateVersion:
        logger.info("[LAB] publish_template_version version_id=%s", version_id)
        version = self.repository.get_template_version(version_id)
        if not version:
            raise LabReportingDomainError(404, "Template version not found")
        if version.status != "DRAFT":
            raise LabReportingDomainError(409, "Only draft versions can be published")

        published = self.repository.get_latest_published_version(version.template_id)
        if published and published.id != version.id:
            published.status = "ARCHIVED"
        version.status = "PUBLISHED"
        version.published_at = datetime.now(UTC)
        self.repository.commit()
        return self.repository.get_template_version(version.id)


    def archive_template_version(self, version_id: int) -> LabReportTemplateVersion:
        logger.info("[LAB] archive_template_version version_id=%s", version_id)
        version = self.repository.get_template_version(version_id)
        if not version:
            raise LabReportingDomainError(404, "Template version not found")
        version.status = "ARCHIVED"
        self.repository.commit()
        return self.repository.get_template_version(version.id)


