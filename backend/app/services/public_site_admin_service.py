"""Business rules for Admin-only website content publication."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crud import clinic as crud_clinic
from app.models.clinic import Doctor
from app.models.service import Service
from app.repositories.services_api_repository import ServicesApiRepository
from app.schemas.public_site_admin import (
    WEBSITE_SLUG_PATTERN,
    WebsiteContentOperation,
    WebsiteDoctorContentOut,
    WebsiteDoctorContentUpdate,
    WebsiteServiceContentOut,
    WebsiteServiceContentUpdate,
)

_UNSET = object()


class WebsiteContentServiceError(Exception):
    """Expected public-content rejection mapped by the API boundary."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        missing_fields: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.missing_fields = missing_fields or []

    def as_detail(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "missing_fields": self.missing_fields,
        }


def _content_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _nonempty(value: str | None) -> bool:
    return bool(value and value.strip())


def _service_missing_fields(
    *,
    active: bool,
    name_ru: str | None,
    name_uz: str | None,
    description_ru: str | None,
    description_uz: str | None,
    slug: str | None,
) -> list[str]:
    missing: list[str] = []
    if not _nonempty(name_ru):
        missing.append("name_ru")
    if not _nonempty(name_uz):
        missing.append("name_uz")
    if not _nonempty(description_ru):
        missing.append("description_ru")
    if not _nonempty(description_uz):
        missing.append("description_uz")
    if not _nonempty(slug):
        missing.append("slug")
    if not active:
        missing.append("active")
    return missing


def _doctor_missing_fields(
    doctor: Doctor,
    *,
    bio_ru: str | None | object = _UNSET,
    bio_uz: str | None | object = _UNSET,
    slug: str | None | object = _UNSET,
) -> list[str]:
    missing: list[str] = []
    user = doctor.user
    display_name = (user.full_name or "").strip() if user else ""
    bio_ru = doctor.bio_ru if bio_ru is _UNSET else bio_ru
    bio_uz = doctor.bio_uz if bio_uz is _UNSET else bio_uz
    slug = doctor.slug if slug is _UNSET else slug
    if not display_name:
        missing.append("display_name")
    if not _nonempty(bio_ru):
        missing.append("bio_ru")
    if not _nonempty(bio_uz):
        missing.append("bio_uz")
    if not _nonempty(slug):
        missing.append("slug")
    if not doctor.active or not user or not user.is_active:
        missing.append("active")
    return missing


def _slug_conflict(exc: IntegrityError, *, entity: str) -> bool:
    original = getattr(exc, "orig", None)
    constraint_name = getattr(getattr(original, "diag", None), "constraint_name", None)
    if constraint_name:
        return constraint_name == f"uq_{entity}_website_slug"
    message = str(original or exc).lower()
    return (
        f"uq_{entity}_website_slug" in message
        or f"{entity}.slug" in message
        or f"{entity}.website_slug" in message
    )


class PublicSiteAdminService:
    """Serialize writes and validate publication without exposing public DTOs."""

    def __init__(
        self,
        db: Session,
        repository: ServicesApiRepository | None = None,
    ) -> None:
        self.db = db
        self.services = repository or ServicesApiRepository(db)

    @staticmethod
    def _service_out(
        service: Service, *, action_result: str | None = None
    ) -> WebsiteServiceContentOut:
        name_ru = service.name
        return WebsiteServiceContentOut(
            id=service.id,
            active=bool(service.active),
            name_ru=name_ru,
            name_uz=service.name_uz,
            description_ru=service.description_ru,
            description_uz=service.description_uz,
            slug=service.slug,
            show_on_website=service.show_on_website,
            website_first_published_at=service.website_first_published_at,
            slug_locked=service.website_first_published_at is not None,
            missing_fields=_service_missing_fields(
                active=bool(service.active),
                name_ru=name_ru,
                name_uz=service.name_uz,
                description_ru=service.description_ru,
                description_uz=service.description_uz,
                slug=service.slug,
            ),
            action_result=action_result,
        )

    @staticmethod
    def _doctor_out(
        doctor: Doctor, *, action_result: str | None = None
    ) -> WebsiteDoctorContentOut:
        user = doctor.user
        return WebsiteDoctorContentOut(
            id=doctor.id,
            active=bool(doctor.active),
            owner_active=bool(user.is_active) if user else None,
            display_name=(user.full_name.strip() or None)
            if user and user.full_name
            else None,
            bio_ru=doctor.bio_ru,
            bio_uz=doctor.bio_uz,
            slug=doctor.slug,
            show_on_website=doctor.show_on_website,
            website_first_published_at=doctor.website_first_published_at,
            slug_locked=doctor.website_first_published_at is not None,
            missing_fields=_doctor_missing_fields(doctor),
            action_result=action_result,
        )

    def list_service_content(self) -> list[WebsiteServiceContentOut]:
        return [
            self._service_out(row)
            for row in self.services.list_services_for_website_admin()
        ]

    def get_service_content(self, service_id: int) -> WebsiteServiceContentOut:
        service = self.services.get_service(service_id)
        if not service:
            raise WebsiteContentServiceError(
                status_code=404,
                code="service_not_found",
                message="Услуга не найдена.",
            )
        return self._service_out(service)

    def get_doctor_content(self, doctor_id: int) -> WebsiteDoctorContentOut:
        doctor = crud_clinic.get_doctor_by_id(self.db, doctor_id)
        if not doctor:
            raise WebsiteContentServiceError(
                status_code=404,
                code="doctor_not_found",
                message="Врач не найден.",
            )
        return self._doctor_out(doctor)

    def update_service_content(
        self,
        service_id: int,
        payload: WebsiteServiceContentUpdate,
    ) -> WebsiteServiceContentOut:
        service = self.services.get_service_for_update(service_id)
        if not service:
            raise WebsiteContentServiceError(
                status_code=404,
                code="service_not_found",
                message="Услуга не найдена.",
            )

        changes = payload.model_dump(exclude_unset=True, exclude={"operation"})
        candidate = {
            "name_ru": service.name,
            "name_uz": service.name_uz,
            "description_ru": service.description_ru,
            "description_uz": service.description_uz,
            "slug": service.slug,
        }
        for field, value in changes.items():
            candidate[field] = _content_text(value) if field != "slug" else value

        if not _nonempty(candidate["name_ru"]):
            raise WebsiteContentServiceError(
                status_code=422,
                code="service_name_required",
                message="Русское название услуги обязательно.",
                missing_fields=["name_ru"],
            )
        self._validate_locked_slug(
            existing_slug=service.slug,
            first_published_at=service.website_first_published_at,
            candidate_slug=candidate["slug"],
        )
        self._validate_unique_service_slug(
            candidate_slug=candidate["slug"], service_id=service.id
        )
        result = self._validate_operation(
            operation=payload.operation,
            is_published=service.show_on_website,
            first_published_at=service.website_first_published_at,
            active=bool(service.active),
            missing_fields=_service_missing_fields(
                active=bool(service.active), **candidate
            ),
        )

        service.name = candidate["name_ru"] or service.name
        service.name_uz = candidate["name_uz"]
        service.description_ru = candidate["description_ru"]
        service.description_uz = candidate["description_uz"]
        service.slug = candidate["slug"]
        self._apply_operation(service, payload.operation)
        return self._commit_service(service, action_result=result)

    def update_doctor_content(
        self,
        doctor_id: int,
        payload: WebsiteDoctorContentUpdate,
    ) -> WebsiteDoctorContentOut:
        doctor = crud_clinic.get_doctor_by_id_for_update(self.db, doctor_id)
        if not doctor:
            raise WebsiteContentServiceError(
                status_code=404,
                code="doctor_not_found",
                message="Врач не найден.",
            )

        changes = payload.model_dump(exclude_unset=True, exclude={"operation"})
        candidate = {
            "bio_ru": doctor.bio_ru,
            "bio_uz": doctor.bio_uz,
            "slug": doctor.slug,
        }
        for field, value in changes.items():
            candidate[field] = _content_text(value) if field != "slug" else value

        self._validate_locked_slug(
            existing_slug=doctor.slug,
            first_published_at=doctor.website_first_published_at,
            candidate_slug=candidate["slug"],
        )
        self._validate_unique_doctor_slug(
            candidate_slug=candidate["slug"], doctor_id=doctor.id
        )
        result = self._validate_operation(
            operation=payload.operation,
            is_published=doctor.show_on_website,
            first_published_at=doctor.website_first_published_at,
            active=bool(doctor.active and doctor.user and doctor.user.is_active),
            missing_fields=_doctor_missing_fields(
                doctor,
                bio_ru=candidate["bio_ru"],
                bio_uz=candidate["bio_uz"],
                slug=candidate["slug"],
            ),
        )

        doctor.bio_ru = candidate["bio_ru"]
        doctor.bio_uz = candidate["bio_uz"]
        doctor.slug = candidate["slug"]
        self._apply_operation(doctor, payload.operation)
        return self._commit_doctor(doctor, action_result=result)

    @staticmethod
    def _validate_locked_slug(
        *,
        existing_slug: str | None,
        first_published_at: datetime | None,
        candidate_slug: str | None,
    ) -> None:
        if first_published_at is not None and candidate_slug != existing_slug:
            raise WebsiteContentServiceError(
                status_code=409,
                code="website_slug_locked",
                message="Адрес страницы закреплён после первой публикации.",
            )
        if candidate_slug is not None and not re.fullmatch(
            WEBSITE_SLUG_PATTERN, candidate_slug
        ):
            raise WebsiteContentServiceError(
                status_code=422,
                code="website_slug_invalid",
                message="Адрес должен содержать латинские строчные буквы, цифры и дефисы.",
                missing_fields=["slug"],
            )

    def _validate_unique_service_slug(
        self, *, candidate_slug: str | None, service_id: int
    ) -> None:
        if candidate_slug and self.services.get_service_website_slug_conflict(
            slug=candidate_slug, exclude_service_id=service_id
        ):
            raise WebsiteContentServiceError(
                status_code=409,
                code="website_slug_conflict",
                message="Этот адрес уже занят другой услугой.",
            )

    def _validate_unique_doctor_slug(
        self, *, candidate_slug: str | None, doctor_id: int
    ) -> None:
        if candidate_slug and crud_clinic.get_doctor_website_slug_conflict(
            self.db, slug=candidate_slug, exclude_doctor_id=doctor_id
        ):
            raise WebsiteContentServiceError(
                status_code=409,
                code="website_slug_conflict",
                message="Этот адрес уже занят другим врачом.",
            )

    @staticmethod
    def _validate_operation(
        *,
        operation: WebsiteContentOperation,
        is_published: bool,
        first_published_at: datetime | None,
        active: bool,
        missing_fields: list[str],
    ) -> str:
        if operation is WebsiteContentOperation.SAVE_DRAFT and is_published:
            raise WebsiteContentServiceError(
                status_code=409,
                code="website_unpublish_before_draft",
                message="Сначала снимите опубликованную карточку с сайта.",
            )
        if operation is WebsiteContentOperation.SAVE_PUBLISHED:
            if not is_published or first_published_at is None:
                raise WebsiteContentServiceError(
                    status_code=409,
                    code="website_not_published",
                    message="Карточка уже не опубликована. Используйте публикацию или повторную публикацию.",
                )
        if operation is WebsiteContentOperation.PUBLISH:
            if is_published or first_published_at is not None:
                raise WebsiteContentServiceError(
                    status_code=409,
                    code="website_not_first_publication",
                    message="Для этой карточки требуется повторная публикация.",
                )
        if operation is WebsiteContentOperation.REPUBLISH:
            if is_published or first_published_at is None:
                raise WebsiteContentServiceError(
                    status_code=409,
                    code="website_not_republishable",
                    message="Карточка ещё не была снята с публикации.",
                )
        if operation is WebsiteContentOperation.UNPUBLISH and not is_published:
            raise WebsiteContentServiceError(
                status_code=409,
                code="website_not_published",
                message="Карточка уже снята с публикации.",
            )
        if operation in {
            WebsiteContentOperation.PUBLISH,
            WebsiteContentOperation.REPUBLISH,
            WebsiteContentOperation.SAVE_PUBLISHED,
        }:
            if not active:
                missing_fields = [*missing_fields, "active"]
            if missing_fields:
                raise WebsiteContentServiceError(
                    status_code=422,
                    code="website_content_incomplete",
                    message="Заполните обязательные данные и проверьте активность записи.",
                    missing_fields=list(dict.fromkeys(missing_fields)),
                )

        return {
            WebsiteContentOperation.SAVE_DRAFT: "draft_saved",
            WebsiteContentOperation.SAVE_PUBLISHED: "published_content_saved",
            WebsiteContentOperation.PUBLISH: "first_published",
            WebsiteContentOperation.UNPUBLISH: "unpublished",
            WebsiteContentOperation.REPUBLISH: "republished",
        }[operation]

    @staticmethod
    def _apply_operation(
        entity: Service | Doctor, operation: WebsiteContentOperation
    ) -> None:
        if operation is WebsiteContentOperation.UNPUBLISH:
            entity.show_on_website = False
        elif operation in {
            WebsiteContentOperation.PUBLISH,
            WebsiteContentOperation.REPUBLISH,
            WebsiteContentOperation.SAVE_PUBLISHED,
        }:
            entity.show_on_website = True
            if entity.website_first_published_at is None:
                entity.website_first_published_at = datetime.now(UTC)
        else:
            entity.show_on_website = False

    def _commit_service(
        self, service: Service, *, action_result: str
    ) -> WebsiteServiceContentOut:
        try:
            self.services.add(service)
            self.services.commit()
            self.services.refresh(service)
        except IntegrityError as exc:
            self.db.rollback()
            if _slug_conflict(exc, entity="services"):
                raise WebsiteContentServiceError(
                    status_code=409,
                    code="website_slug_conflict",
                    message="Этот адрес уже занят другой услугой.",
                ) from exc
            raise
        return self._service_out(service, action_result=action_result)

    def _commit_doctor(
        self, doctor: Doctor, *, action_result: str
    ) -> WebsiteDoctorContentOut:
        try:
            self.db.add(doctor)
            self.db.commit()
            self.db.refresh(doctor)
        except IntegrityError as exc:
            self.db.rollback()
            if _slug_conflict(exc, entity="doctors"):
                raise WebsiteContentServiceError(
                    status_code=409,
                    code="website_slug_conflict",
                    message="Этот адрес уже занят другим врачом.",
                ) from exc
            raise
        return self._doctor_out(doctor, action_result=action_result)
