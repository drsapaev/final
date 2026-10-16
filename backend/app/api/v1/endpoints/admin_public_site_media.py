"""Admin-only management for public website images."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import require_roles
from app.models.user import User
from app.schemas.public_site_media import (
    PublicSiteMediaAdminOut,
    PublicSiteMediaErrorOut,
    PublicSiteMediaKind,
)
from app.services.public_site_media_service import (
    PublicSiteMediaError,
    PublicSiteMediaService,
)

router = APIRouter()

_MEDIA_ERROR_RESPONSES = {
    400: {
        "model": PublicSiteMediaErrorOut,
        "description": "Invalid image or media ownership.",
    },
    404: {
        "model": PublicSiteMediaErrorOut,
        "description": "Media or doctor was not found.",
    },
    409: {
        "model": PublicSiteMediaErrorOut,
        "description": "Media state conflicts with the requested operation.",
    },
    413: {"model": PublicSiteMediaErrorOut, "description": "Image is too large."},
    500: {
        "model": PublicSiteMediaErrorOut,
        "description": "The media operation failed.",
    },
    503: {
        "model": PublicSiteMediaErrorOut,
        "description": "Media storage is unavailable.",
    },
}


def _raise_media_error(exc: PublicSiteMediaError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code},
    ) from exc


@router.get(
    "/public-site/media",
    response_model=list[PublicSiteMediaAdminOut],
    operation_id="admin_list_public_site_media",
    summary="Получить список логотипов и фотографий для сайта",
)
def list_public_site_media(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("Admin")),
) -> list[dict[str, object]]:
    return PublicSiteMediaService(db).list_admin_media()


@router.post(
    "/public-site/media",
    response_model=PublicSiteMediaAdminOut,
    responses=_MEDIA_ERROR_RESPONSES,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_upload_public_site_media",
    summary="Загрузить логотип или фотографию врача",
)
def upload_public_site_media(
    file: Annotated[UploadFile, File(...)],
    asset_kind: Annotated[PublicSiteMediaKind, Form(...)],
    doctor_id: Annotated[int | None, Form()] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
) -> dict[str, object]:
    try:
        raw = file.file.read(settings.PUBLIC_SITE_MEDIA_MAX_UPLOAD_BYTES + 1)
        service = PublicSiteMediaService(db)
        media = service.upload(
            raw=raw,
            asset_kind=asset_kind,
            doctor_id=doctor_id,
            actor_user_id=current_user.id,
        )
        return service.list_admin_media_item(media)
    except PublicSiteMediaError as exc:
        _raise_media_error(exc)


@router.put(
    "/public-site/media/{media_id}/publish",
    response_model=PublicSiteMediaAdminOut,
    responses=_MEDIA_ERROR_RESPONSES,
    operation_id="admin_publish_public_site_media",
    summary="Опубликовать изображение на сайте",
)
def publish_public_site_media(
    media_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
) -> dict[str, object]:
    try:
        service = PublicSiteMediaService(db)
        media = service.publish(media_id=media_id, actor_user_id=current_user.id)
        return service.list_admin_media_item(media)
    except PublicSiteMediaError as exc:
        _raise_media_error(exc)


@router.put(
    "/public-site/media/{media_id}/unpublish",
    response_model=PublicSiteMediaAdminOut,
    responses=_MEDIA_ERROR_RESPONSES,
    operation_id="admin_unpublish_public_site_media",
    summary="Снять изображение с сайта",
)
def unpublish_public_site_media(
    media_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
) -> dict[str, object]:
    try:
        service = PublicSiteMediaService(db)
        media = service.unpublish(media_id=media_id, actor_user_id=current_user.id)
        return service.list_admin_media_item(media)
    except PublicSiteMediaError as exc:
        _raise_media_error(exc)
