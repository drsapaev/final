"""Public website read contract and publication filtering."""

from __future__ import annotations

from decimal import Decimal

from app.models.clinic import ClinicSettings, Doctor, ServiceCategory
from app.models.medical_specialty import MedicalSpecialty
from app.models.service import Service
from app.models.user import User


def _category(db_session, code: str, *, active: bool = True) -> ServiceCategory:
    row = ServiceCategory(
        code=code,
        name_ru=f"Категория {code}",
        name_uz=f"Turkum {code}",
        active=active,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _service(
    db_session,
    slug: str,
    *,
    category: ServiceCategory | None = None,
    active: bool = True,
    published: bool = True,
    price: Decimal | None = Decimal("125000.00"),
    currency: str | None = "UZS",
) -> Service:
    row = Service(
        name=f"SYNTHETIC service {slug}",
        name_uz=f"SYNTHETIC xizmat {slug}",
        description_ru=f"SYNTHETIC описание {slug}",
        description_uz=f"SYNTHETIC tavsif {slug}",
        slug=slug,
        show_on_website=published,
        active=active,
        price=price,
        currency=currency,
        category=category,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    if currency is None:
        # SQLAlchemy applies the model's Python-side UZS default to an
        # explicitly passed None; override it after INSERT to exercise the
        # nullable legacy-data path.
        row.currency = None
        db_session.commit()
        db_session.refresh(row)
    return row


def _doctor(
    db_session,
    slug: str,
    *,
    specialty: str = "synthetic-public-specialty",
    active: bool = True,
    published: bool = True,
) -> Doctor:
    username = f"synthetic_public_site_{slug.replace('-', '_')}"
    user = User(
        username=username,
        email=f"{username}@example.test",
        full_name=f"SYNTHETIC Website Doctor {slug}",
        hashed_password="synthetic-unused-password",
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    row = Doctor(
        user_id=user.id,
        specialty=specialty,
        active=active,
        show_on_website=published,
        bio_ru=f"SYNTHETIC биография {slug}",
        bio_uz=f"SYNTHETIC tarjimai hol {slug}",
        slug=slug,
        cabinet="Private room",
        price_default=Decimal("999999.00"),
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_public_catalog_filters_and_allowlists(client, db_session):
    active_category = _category(db_session, "synthetic-active")
    inactive_category = _category(db_session, "synthetic-inactive", active=False)
    _category(db_session, "synthetic-empty")
    _service(
        db_session,
        "categorized",
        category=active_category,
        price=Decimal("250000.00"),
    )
    _service(db_session, "no-category", price=None)
    _service(
        db_session,
        "no-currency",
        price=Decimal("50000.00"),
        currency=None,
    )
    _service(
        db_session,
        "inactive-category",
        category=inactive_category,
        price=Decimal("50000.00"),
    )
    _service(db_session, "inactive-service", active=False)
    _service(db_session, "draft", published=False)
    incomplete_translation = _service(db_session, "incomplete-translation")
    incomplete_translation.description_uz = " "
    db_session.commit()

    clinic_values = {
        "clinic_name": "SYNTHETIC Doktor KosMed",
        "clinic_address": "SYNTHETIC address",
        "clinic_phone": "SYNTHETIC clinic phone",
        "clinic_email": "synthetic@example.test",
        "clinic_logo_url": "https://private.invalid/logo.png",
        "queue_settings": {"private": "must not be exposed"},
    }
    for key, value in clinic_values.items():
        db_session.add(ClinicSettings(key=key, value=value, category="clinic"))
    db_session.commit()

    clinic_response = client.get("/api/v1/public-site/clinic")
    assert clinic_response.status_code == 200
    clinic = clinic_response.json()
    assert clinic == {
        "name": "SYNTHETIC Doktor KosMed",
        "address": "SYNTHETIC address",
        "phone": "SYNTHETIC clinic phone",
        "email": "synthetic@example.test",
    }

    response = client.get(
        "/api/v1/public-site/services",
        params={"locale": "uz-Latn"},
    )
    assert response.status_code == 200, response.text
    services = {item["slug"]: item for item in response.json()}
    assert set(services) == {
        "categorized",
        "inactive-category",
        "no-currency",
        "no-category",
    }
    assert services["categorized"]["name"].startswith("SYNTHETIC xizmat")
    assert services["categorized"]["category"] == active_category.name_uz
    assert services["categorized"]["price"] == "250000.00"
    assert services["no-category"]["price"] is None
    assert services["no-category"]["category"] is None
    assert services["no-currency"]["price"] is None
    assert services["no-currency"]["currency"] is None
    assert services["inactive-category"]["category"] is None
    assert set(services["categorized"]) == {
        "slug",
        "name",
        "description",
        "price",
        "currency",
        "category",
    }

    russian = client.get(
        "/api/v1/public-site/services/categorized",
        params={"locale": "ru"},
    )
    assert russian.status_code == 200
    assert russian.json()["name"].startswith("SYNTHETIC service")
    assert russian.json()["description"].startswith("SYNTHETIC описание")

    categories = client.get(
        "/api/v1/public-site/categories",
        params={"locale": "uz-Latn"},
    )
    assert categories.status_code == 200
    assert categories.json() == [{"name": active_category.name_uz}]


def test_public_doctor_omits_untranslated_specialty_and_internal_fields(
    client, db_session
):
    db_session.add(
        MedicalSpecialty(
            code="synthetic-public-specialty",
            title_ru="SYNTHETIC специальность",
            title_uz=None,
            title_en=None,
            active=False,
        )
    )
    db_session.commit()
    doctor = _doctor(db_session, "published-doctor")
    _doctor(db_session, "draft-doctor", published=False)
    _doctor(db_session, "inactive-doctor", active=False)

    uzbek = client.get(
        f"/api/v1/public-site/doctors/{doctor.slug}",
        params={"locale": "uz-Latn"},
    )
    assert uzbek.status_code == 200, uzbek.text
    uzbek_body = uzbek.json()
    assert uzbek_body["specialty"] is None
    assert set(uzbek_body) == {"slug", "name", "bio", "specialty"}
    assert "synthetic-public-specialty" not in uzbek.text
    assert "cabinet" not in uzbek.text
    assert "price_default" not in uzbek.text

    russian = client.get(
        f"/api/v1/public-site/doctors/{doctor.slug}",
        params={"locale": "ru"},
    )
    assert russian.status_code == 200
    assert russian.json()["specialty"] == "SYNTHETIC специальность"

    doctors = client.get(
        "/api/v1/public-site/doctors",
        params={"locale": "uz-Latn"},
    )
    assert doctors.status_code == 200
    assert [row["slug"] for row in doctors.json()] == [doctor.slug]


def test_hidden_and_unknown_details_share_public_not_found_response(client, db_session):
    _service(db_session, "hidden-service", published=False)
    hidden_service = client.get(
        "/api/v1/public-site/services/hidden-service",
        params={"locale": "ru"},
    )
    unknown_service = client.get(
        "/api/v1/public-site/services/unknown-service",
        params={"locale": "ru"},
    )
    assert hidden_service.status_code == unknown_service.status_code == 404
    assert hidden_service.json() == unknown_service.json()

    hidden_doctor = _doctor(db_session, "hidden-doctor", published=False)
    hidden_doctor_response = client.get(
        f"/api/v1/public-site/doctors/{hidden_doctor.slug}",
        params={"locale": "ru"},
    )
    unknown_doctor_response = client.get(
        "/api/v1/public-site/doctors/unknown-doctor",
        params={"locale": "ru"},
    )
    assert (
        hidden_doctor_response.status_code == unknown_doctor_response.status_code == 404
    )
    assert hidden_doctor_response.json() == unknown_doctor_response.json()


def test_public_catalog_requires_a_supported_locale(client):
    missing_locale = client.get("/api/v1/public-site/services")
    unsupported_locale = client.get(
        "/api/v1/public-site/services",
        params={"locale": "en"},
    )
    assert missing_locale.status_code == 422
    assert unsupported_locale.status_code == 422


def test_public_site_openapi_contract_is_allowlisted(client):
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    components = schema["components"]["schemas"]

    expected_paths = {
        "/api/v1/public-site/clinic": "public_site_get_clinic",
        "/api/v1/public-site/services": "public_site_list_services",
        "/api/v1/public-site/services/{slug}": "public_site_get_service",
        "/api/v1/public-site/categories": "public_site_list_categories",
        "/api/v1/public-site/doctors": "public_site_list_doctors",
        "/api/v1/public-site/doctors/{slug}": "public_site_get_doctor",
    }
    for path, operation_id in expected_paths.items():
        operation = paths[path]["get"]
        assert operation["operationId"] == operation_id
        assert "security" not in operation

    locale_parameter = paths["/api/v1/public-site/services"]["get"]["parameters"][0]
    assert locale_parameter["name"] == "locale"
    assert locale_parameter["required"] is True
    assert locale_parameter["schema"]["enum"] == ["uz-Latn", "ru"]

    assert set(components["PublicSiteClinicOut"]["properties"]) == {
        "name",
        "address",
        "phone",
        "email",
    }
    assert set(components["PublicSiteServiceOut"]["properties"]) == {
        "slug",
        "name",
        "description",
        "price",
        "currency",
        "category",
    }
    assert set(components["PublicSiteDoctorOut"]["properties"]) == {
        "slug",
        "name",
        "bio",
        "specialty",
    }
    assert set(components["PublicSiteCategoryOut"]["properties"]) == {"name"}
