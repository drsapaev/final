"""Read-only public website endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories.public_site_read_repository import PublicSiteReadRepository
from app.schemas.public_site import (
    PublicSiteCategoryOut,
    PublicSiteClinicOut,
    PublicSiteDoctorOut,
    PublicSiteLocale,
    PublicSiteNotFoundOut,
    PublicSiteServiceOut,
)
from app.schemas.public_site_media import PublicSiteMediaErrorOut
from app.services.public_site_media_service import (
    PublicSiteMediaError,
    PublicSiteMediaService,
)
from app.services.public_site_read_service import PublicSiteReadService

router = APIRouter()


def _read_service(db: Session) -> PublicSiteReadService:
    return PublicSiteReadService(PublicSiteReadRepository(db))


def _public_not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "public_content_not_found"},
    )


@router.get(
    "/media/{storage_key}",
    response_class=Response,
    responses={
        200: {
            "description": "Published JPEG, PNG, or WebP image.",
            "content": {
                media_type: {"schema": {"type": "string", "format": "binary"}}
                for media_type in ("image/jpeg", "image/png", "image/webp")
            },
        },
        404: {
            "model": PublicSiteNotFoundOut,
            "description": "Published media was not found.",
        },
        503: {
            "model": PublicSiteMediaErrorOut,
            "description": "Public media storage is unavailable.",
        },
    },
    operation_id="public_site_get_media",
    summary="Получить явно опубликованное изображение сайта",
)
def get_public_media(storage_key: str, db: Session = Depends(get_db)) -> Response:
    try:
        payload = PublicSiteMediaService(db).get_public_asset(storage_key)
    except PublicSiteMediaError as exc:
        if exc.status_code == 404:
            raise _public_not_found() from exc
        raise HTTPException(
            status_code=503,
            detail={"code": "public_media_unavailable"},
        ) from exc
    if payload is None:
        raise _public_not_found()
    return Response(
        content=payload.body,
        media_type=payload.mime_type,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/clinic",
    response_model=PublicSiteClinicOut,
    operation_id="public_site_get_clinic",
    summary="Получить публичные контакты клиники",
)
def get_public_clinic(db: Session = Depends(get_db)) -> PublicSiteClinicOut:
    return _read_service(db).get_clinic()


@router.get(
    "/services",
    response_model=list[PublicSiteServiceOut],
    operation_id="public_site_list_services",
    summary="Получить опубликованные услуги",
)
def list_public_services(
    locale: PublicSiteLocale = Query(...),
    db: Session = Depends(get_db),
) -> list[PublicSiteServiceOut]:
    return _read_service(db).list_services(locale)


@router.get(
    "/services/{slug}",
    response_model=PublicSiteServiceOut,
    responses={
        404: {
            "model": PublicSiteNotFoundOut,
            "description": "Published service was not found.",
        }
    },
    operation_id="public_site_get_service",
    summary="Получить опубликованную услугу",
)
def get_public_service(
    slug: str,
    locale: PublicSiteLocale = Query(...),
    db: Session = Depends(get_db),
) -> PublicSiteServiceOut:
    service = _read_service(db).get_service(slug, locale)
    if service is None:
        raise _public_not_found()
    return service


@router.get(
    "/categories",
    response_model=list[PublicSiteCategoryOut],
    operation_id="public_site_list_categories",
    summary="Получить категории опубликованных услуг",
)
def list_public_categories(
    locale: PublicSiteLocale = Query(...),
    db: Session = Depends(get_db),
) -> list[PublicSiteCategoryOut]:
    return _read_service(db).list_categories(locale)


@router.get(
    "/doctors",
    response_model=list[PublicSiteDoctorOut],
    operation_id="public_site_list_doctors",
    summary="Получить опубликованных врачей",
)
def list_public_doctors(
    locale: PublicSiteLocale = Query(...),
    db: Session = Depends(get_db),
) -> list[PublicSiteDoctorOut]:
    return _read_service(db).list_doctors(locale)


@router.get(
    "/doctors/{slug}",
    response_model=PublicSiteDoctorOut,
    responses={
        404: {
            "model": PublicSiteNotFoundOut,
            "description": "Published doctor was not found.",
        }
    },
    operation_id="public_site_get_doctor",
    summary="Получить опубликованного врача",
)
def get_public_doctor(
    slug: str,
    locale: PublicSiteLocale = Query(...),
    db: Session = Depends(get_db),
) -> PublicSiteDoctorOut:
    doctor = _read_service(db).get_doctor(slug, locale)
    if doctor is None:
        raise _public_not_found()
    return doctor
