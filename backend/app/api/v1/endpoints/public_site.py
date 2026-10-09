"""Read-only public website endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories.public_site_read_repository import PublicSiteReadRepository
from app.schemas.public_site import (
    PublicSiteCategoryOut,
    PublicSiteClinicOut,
    PublicSiteDoctorOut,
    PublicSiteLocale,
    PublicSiteServiceOut,
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
