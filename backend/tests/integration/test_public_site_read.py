"""Public website read contract and publication filtering."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import event

from app.models.clinic import ClinicSettings, Doctor, ServiceCategory
from app.models.department import Department, DepartmentService
from app.models.medical_specialty import MedicalSpecialty
from app.models.online_queue import QueueResource
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
    experience_years: int | None = None,
    professional_category: str | None = None,
    department_id: int | None = None,
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
        department_id=department_id,
        specialty=specialty,
        experience_years=experience_years,
        professional_category=professional_category,
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
        "clinic_working_hours_start": "09:00",
        "clinic_working_hours_end": "17:00",
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
        "logo_url": None,
        "working_hours_start": "09:00:00",
        "working_hours_end": "17:00:00",
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
    detail = russian.json()
    assert detail["name"].startswith("SYNTHETIC service")
    assert detail["description"].startswith("SYNTHETIC описание")
    assert detail["related_doctors"] == []
    assert set(detail) == set(services["categorized"]) | {"related_doctors"}

    categories = client.get(
        "/api/v1/public-site/categories",
        params={"locale": "uz-Latn"},
    )
    assert categories.status_code == 200
    assert categories.json() == [{"name": active_category.name_uz}]


def test_service_detail_lists_eligible_published_doctors_with_bounded_reads(
    client, db_session
):
    primary = Department(key="cardiology", name_ru="SYNTHETIC primary")
    secondary = Department(key="cardio", name_ru="SYNTHETIC secondary")
    unrelated = Department(key="cardiology_common", name_ru="SYNTHETIC unrelated")
    conflicting = Department(key="dentistry", name_ru="SYNTHETIC conflicting")
    db_session.add_all([primary, secondary, unrelated, conflicting])
    db_session.flush()
    primary_id, secondary_id, unrelated_id = primary.id, secondary.id, unrelated.id
    conflicting_id = conflicting.id

    service = _service(db_session, "linked-service")
    service.requires_doctor = True
    service.department_key = "cardiology"
    db_session.add_all(
        [
            DepartmentService(service_id=service.id, department_id=department_id)
            for department_id in (primary_id, secondary_id, conflicting_id)
        ]
    )
    _doctor(db_session, "a-cardio", specialty="cardio", department_id=primary_id)

    connection = db_session.connection()

    def read_related_doctors(locale):
        select_count = 0

        def count_selects(conn, cursor, statement, parameters, context, executemany):
            nonlocal select_count
            if statement.lstrip().upper().startswith("SELECT"):
                select_count += 1

        db_session.expire_all()
        event.listen(connection, "before_cursor_execute", count_selects)
        try:
            response = client.get(
                "/api/v1/public-site/services/linked-service",
                params={"locale": locale},
            )
        finally:
            event.remove(connection, "before_cursor_execute", count_selects)
        assert response.status_code == 200, response.text
        return response.json()["related_doctors"], select_count

    first_profile = {"slug": "a-cardio", "name": "SYNTHETIC Website Doctor a-cardio"}
    baseline, baseline_reads = read_related_doctors("ru")
    assert baseline == [first_profile]
    assert baseline_reads > 0

    _doctor(
        db_session, "b-cardio", specialty="Cardiologist", department_id=secondary_id
    )
    _doctor(
        db_session, "other-department", specialty="cardio", department_id=unrelated_id
    )
    _doctor(
        db_session, "wrong-specialty", specialty="dentistry", department_id=primary_id
    )
    _doctor(
        db_session,
        "wrong-department-key",
        specialty="cardio",
        department_id=conflicting_id,
    )
    _doctor(db_session, "no-department", specialty="cardio")
    _doctor(
        db_session,
        "inactive",
        specialty="cardio",
        department_id=primary_id,
        active=False,
    )
    _doctor(
        db_session,
        "hidden",
        specialty="cardio",
        department_id=primary_id,
        published=False,
    )
    incomplete = _doctor(
        db_session, "incomplete", specialty="cardio", department_id=secondary_id
    )
    incomplete.bio_uz = "\t"
    wrong_role = _doctor(
        db_session, "staff-profile", specialty="cardio", department_id=primary_id
    )
    wrong_role.user.role = "Registrar"
    inactive_user = _doctor(
        db_session, "inactive-user", specialty="cardio", department_id=secondary_id
    )
    inactive_user.user.is_active = False
    _doctor(db_session, "invalid-slug-", specialty="cardio", department_id=secondary_id)
    db_session.commit()

    expected = [
        first_profile,
        {"slug": "b-cardio", "name": "SYNTHETIC Website Doctor b-cardio"},
    ]
    for locale in ("ru", "uz-Latn"):
        doctors, reads = read_related_doctors(locale)
        assert doctors == expected
        assert reads == baseline_reads

    service.department_id = primary_id
    db_session.commit()
    assert read_related_doctors("ru")[0] == [first_profile]

    service.department_id = unrelated_id
    db_session.commit()
    assert read_related_doctors("ru")[0] == []


def test_service_detail_respects_doctor_pin_without_falling_back(client, db_session):
    service = _service(db_session, "pinned-service")
    doctor = _doctor(db_session, "pinned-doctor", specialty="cardio")
    _doctor(db_session, "other-cardiologist", specialty="cardio")
    service.department_key = "cardiology"
    service.doctor_id = doctor.id
    db_session.commit()

    path = "/api/v1/public-site/services/pinned-service"
    response = client.get(path, params={"locale": "ru"})
    assert response.status_code == 200, response.text
    assert response.json()["related_doctors"] == [
        {"slug": "pinned-doctor", "name": "SYNTHETIC Website Doctor pinned-doctor"}
    ]

    doctor.show_on_website = False
    db_session.commit()
    response = client.get(path, params={"locale": "ru"})
    assert response.status_code == 200, response.text
    assert response.json()["related_doctors"] == []


def test_service_detail_requires_a_configured_clinician_route(client, db_session):
    service = _service(db_session, "routing-service")
    _doctor(db_session, "legacy-cardiologist", specialty="Cardiologist")
    service.requires_doctor = True

    def read_related_doctors():
        db_session.commit()
        response = client.get(
            "/api/v1/public-site/services/routing-service", params={"locale": "ru"}
        )
        assert response.status_code == 200, response.text
        return response.json()["related_doctors"]

    assert read_related_doctors() == []

    service.department_key = "cardio"
    expected = [
        {
            "slug": "legacy-cardiologist",
            "name": "SYNTHETIC Website Doctor legacy-cardiologist",
        }
    ]
    assert read_related_doctors() == expected

    service.requires_doctor = False
    assert read_related_doctors() == []

    service.is_consultation = True
    assert read_related_doctors() == []

    resource = QueueResource(
        code="synthetic_public_site_resource",
        queue_tag="synthetic-public-site-resource",
        display_name="SYNTHETIC public site resource",
        active=True,
    )
    db_session.add(resource)
    service.queue_tag = resource.queue_tag
    assert read_related_doctors() == []

    service.is_consultation = False
    service.requires_doctor = True
    assert read_related_doctors() == []

    resource.active = False
    assert read_related_doctors() == expected


def test_malformed_published_services_are_omitted_and_details_are_not_found(
    client, db_session
):
    valid = _service(db_session, "valid-service")
    tab_only = _service(db_session, "tab-only-description")
    tab_only.description_ru = "\t"
    newline_only = _service(db_session, "newline-only-description")
    newline_only.description_uz = "\r\n"
    db_session.commit()

    expected_not_found = {"detail": {"code": "public_content_not_found"}}
    for locale in ("ru", "uz-Latn"):
        response = client.get(
            "/api/v1/public-site/services",
            params={"locale": locale},
        )
        assert response.status_code == 200, response.text
        assert [row["slug"] for row in response.json()] == [valid.slug]

        for slug in (tab_only.slug, newline_only.slug):
            malformed_detail = client.get(
                f"/api/v1/public-site/services/{slug}",
                params={"locale": locale},
            )
            unknown_detail = client.get(
                "/api/v1/public-site/services/unknown-service",
                params={"locale": locale},
            )
            assert malformed_detail.status_code == 404
            assert malformed_detail.json() == expected_not_found
            assert malformed_detail.json() == unknown_detail.json()


def test_malformed_published_doctors_are_omitted_and_details_are_not_found(
    client, db_session
):
    valid = _doctor(db_session, "valid-doctor")
    tab_only_bio = _doctor(db_session, "tab-only-bio")
    tab_only_bio.bio_ru = "\t"
    newline_only_bio = _doctor(db_session, "newline-only-bio")
    newline_only_bio.bio_uz = "\n"
    blank_display_name = _doctor(db_session, "blank-display-name")
    assert blank_display_name.user is not None
    blank_display_name.user.full_name = "\t\r\n"
    db_session.commit()

    expected_not_found = {"detail": {"code": "public_content_not_found"}}
    malformed_slugs = (
        tab_only_bio.slug,
        newline_only_bio.slug,
        blank_display_name.slug,
    )
    for locale in ("ru", "uz-Latn"):
        response = client.get(
            "/api/v1/public-site/doctors",
            params={"locale": locale},
        )
        assert response.status_code == 200, response.text
        assert [row["slug"] for row in response.json()] == [valid.slug]

        for slug in malformed_slugs:
            malformed_detail = client.get(
                f"/api/v1/public-site/doctors/{slug}",
                params={"locale": locale},
            )
            unknown_detail = client.get(
                "/api/v1/public-site/doctors/unknown-doctor",
                params={"locale": locale},
            )
            assert malformed_detail.status_code == 404
            assert malformed_detail.json() == expected_not_found
            assert malformed_detail.json() == unknown_detail.json()


def test_public_categories_are_unique_by_localized_display_name(client, db_session):
    first_category = _category(db_session, "synthetic-same-label-a")
    second_category = _category(db_session, "synthetic-same-label-b")
    first_category.name_ru = second_category.name_ru = "SYNTHETIC Общая категория"
    first_category.name_uz = "SYNTHETIC Birinchi turkum"
    second_category.name_uz = "SYNTHETIC Ikkinchi turkum"
    db_session.commit()
    _service(db_session, "same-label-service-a", category=first_category)
    _service(db_session, "same-label-service-b", category=second_category)

    russian = client.get(
        "/api/v1/public-site/categories",
        params={"locale": "ru"},
    )
    uzbek = client.get(
        "/api/v1/public-site/categories",
        params={"locale": "uz-Latn"},
    )
    assert russian.status_code == uzbek.status_code == 200
    assert russian.json() == [{"name": "SYNTHETIC Общая категория"}]
    assert {row["name"] for row in uzbek.json()} == {
        "SYNTHETIC Birinchi turkum",
        "SYNTHETIC Ikkinchi turkum",
    }


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
    doctor = _doctor(
        db_session,
        "published-doctor",
        experience_years=18,
        professional_category="highest",
    )
    _doctor(db_session, "draft-doctor", published=False)
    _doctor(db_session, "inactive-doctor", active=False)

    uzbek = client.get(
        f"/api/v1/public-site/doctors/{doctor.slug}",
        params={"locale": "uz-Latn"},
    )
    assert uzbek.status_code == 200, uzbek.text
    uzbek_body = uzbek.json()
    assert uzbek_body["specialty"] is None
    assert uzbek_body["experience_years"] == 18
    assert uzbek_body["professional_category"] == "Oliy malaka toifasi"
    assert uzbek_body["portrait_url"] is None
    assert set(uzbek_body) == {
        "slug",
        "name",
        "bio",
        "specialty",
        "experience_years",
        "professional_category",
        "portrait_url",
    }
    assert "synthetic-public-specialty" not in uzbek.text
    assert "cabinet" not in uzbek.text
    assert "price_default" not in uzbek.text

    russian = client.get(
        f"/api/v1/public-site/doctors/{doctor.slug}",
        params={"locale": "ru"},
    )
    assert russian.status_code == 200
    assert russian.json()["specialty"] == "SYNTHETIC специальность"
    assert russian.json()["experience_years"] == 18
    assert (
        russian.json()["professional_category"] == "Высшая квалификационная категория"
    )

    doctors = client.get(
        "/api/v1/public-site/doctors",
        params={"locale": "uz-Latn"},
    )
    assert doctors.status_code == 200
    assert [row["slug"] for row in doctors.json()] == [doctor.slug]
    assert doctors.json()[0]["experience_years"] == 18
    assert doctors.json()[0]["professional_category"] == "Oliy malaka toifasi"


def test_hidden_and_unknown_details_share_public_not_found_response(client, db_session):
    expected_not_found = {"detail": {"code": "public_content_not_found"}}
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
    assert hidden_service.json() == unknown_service.json() == expected_not_found

    hidden_doctor = _doctor(
        db_session,
        "hidden-doctor",
        published=False,
        professional_category="highest",
    )
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
    assert (
        hidden_doctor_response.json()
        == unknown_doctor_response.json()
        == expected_not_found
    )


def test_public_catalog_requires_a_supported_locale(client):
    missing_locale = client.get("/api/v1/public-site/services")
    unsupported_locale = client.get(
        "/api/v1/public-site/services",
        params={"locale": "en"},
    )
    assert missing_locale.status_code == 422
    assert unsupported_locale.status_code == 422


def test_public_clinic_hours_use_approved_defaults_and_hide_invalid_overrides(
    client, db_session
):
    default_hours = client.get("/api/v1/public-site/clinic").json()
    assert default_hours["working_hours_start"] == "09:00:00"
    assert default_hours["working_hours_end"] == "17:00:00"

    db_session.add_all(
        [
            ClinicSettings(
                key="clinic_working_hours_start", value="25:00", category="clinic"
            ),
            ClinicSettings(
                key="clinic_working_hours_end", value="17:00", category="clinic"
            ),
        ]
    )
    db_session.commit()
    invalid_hours = client.get("/api/v1/public-site/clinic").json()
    assert invalid_hours["working_hours_start"] is None
    assert invalid_hours["working_hours_end"] is None


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
        "/api/v1/public-site/media/{storage_key}": "public_site_get_media",
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
        "logo_url",
        "working_hours_start",
        "working_hours_end",
    }
    assert set(components["PublicSiteServiceOut"]["properties"]) == {
        "slug",
        "name",
        "description",
        "price",
        "currency",
        "category",
    }
    list_schema = paths["/api/v1/public-site/services"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]
    assert list_schema["items"]["$ref"] == "#/components/schemas/PublicSiteServiceOut"
    detail_schema = paths["/api/v1/public-site/services/{slug}"]["get"]["responses"][
        "200"
    ]["content"]["application/json"]["schema"]
    assert detail_schema["$ref"] == "#/components/schemas/PublicSiteServiceDetailOut"
    detail_properties = components["PublicSiteServiceDetailOut"]["properties"]
    assert set(detail_properties) == set(
        components["PublicSiteServiceOut"]["properties"]
    ) | {"related_doctors"}
    related_doctors = detail_properties["related_doctors"]
    assert related_doctors["type"] == "array"
    item_schema = components[related_doctors["items"]["$ref"].split("/")[-1]]
    assert (
        set(item_schema["properties"])
        == set(item_schema["required"])
        == {"slug", "name"}
    )
    assert set(components["PublicSiteDoctorOut"]["properties"]) == {
        "slug",
        "name",
        "bio",
        "specialty",
        "experience_years",
        "professional_category",
        "portrait_url",
    }
    assert set(components["PublicSiteCategoryOut"]["properties"]) == {"name"}
