from decimal import Decimal

import pytest

from app.models.clinic import ServiceCategory
from app.models.service import Service


@pytest.mark.integration
def test_registrar_services_prefers_explicit_lab_routing_over_code_fallback(
    client,
    db_session,
    admin_user,
    admin_password,
):
    lab_category = ServiceCategory(
        code="lab-adm-06",
        name_ru="Лабораторная категория ADM-06",
        specialty="laboratory",
        active=True,
    )
    db_session.add(lab_category)
    db_session.commit()
    db_session.refresh(lab_category)

    service = Service(
        name="ADM-06 Лабораторная услуга",
        code="P77",
        service_code="P77",
        category_code="P",
        category_id=lab_category.id,
        queue_tag="lab",
        department_key="lab",
        price=Decimal("15000.00"),
        currency="UZS",
        duration_minutes=30,
        active=True,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)

    from tests.conftest import mint_access_token

    headers = {"Authorization": f"Bearer {mint_access_token(admin_user)}"}
    response = client.get("/api/v1/registrar/services", headers=headers)

    assert response.status_code == 200, response.text
    payload = response.json()["services_by_group"]

    laboratory_rows = [row for row in payload["laboratory"] if row["id"] == service.id]
    procedures_rows = [row for row in payload["procedures"] if row["id"] == service.id]

    assert len(laboratory_rows) == 1
    assert laboratory_rows[0]["group"] == "laboratory"
    assert laboratory_rows[0]["queue_tag"] == "lab"
    assert laboratory_rows[0]["department_key"] == "lab"
    assert procedures_rows == []


@pytest.mark.integration
def test_registrar_services_emits_accepted_specialties_from_server_eligibility(
    client,
    db_session,
    admin_user,
    admin_password,
):
    """RQ-08.a: UI-потребление серверной eligibility.

    Каталог регистратуры обязан отдаёт per-service accepted_specialties -
    допустимые специальности врача для department_key, вычисленные ТОЙ ЖЕ
    функцией (_accepted_specialty_variants_for_department_key, RQ-05.a),
    что и серверный гейт корзины. Тогда фронтовый filterDoctorsForService
    больше не зависит от собственной копии alias-таблицы: список UI и
    запрет сервера буквально совпадают.

    Пины:
    - dental-услуга: весь семейство вариантов (реверсивный канон
      "dental" -> dentistry-семейство, RQ-05.a);
    - услуга без department_key: accepted_specialties = None
      (проверка специальности неприменима, как в гейте);
    - lab-услуга: {"lab", "laboratory"}.
    """
    dental_service = Service(
        name="RQ-08a Стоматологическая услуга",
        code="D88a",
        service_code="D88a",
        category_code="S",
        department_key="dental",
        price=Decimal("10000.00"),
        currency="UZS",
        duration_minutes=30,
        active=True,
    )
    plain_service = Service(
        name="RQ-08a Услуга без отделения",
        code="P88a",
        service_code="P88a",
        category_code="O",
        price=Decimal("5000.00"),
        currency="UZS",
        duration_minutes=30,
        active=True,
    )
    db_session.add_all([dental_service, plain_service])
    db_session.commit()
    db_session.refresh(dental_service)
    db_session.refresh(plain_service)

    from tests.conftest import mint_access_token

    headers = {"Authorization": f"Bearer {mint_access_token(admin_user)}"}
    response = client.get("/api/v1/registrar/services", headers=headers)

    assert response.status_code == 200, response.text
    payload = response.json()["services_by_group"]
    rows = {
        row["id"]: row
        for group_rows in payload.values()
        for row in group_rows
    }

    dental_row = rows[dental_service.id]
    # Реверсивный канон RQ-05.a: "dental" - не ключ SSOT-таблицы, но входит
    # в варианты канона "dentistry"; set lowercased + отсортирован.
    assert dental_row["department_key"] == "dental"
    assert dental_row["accepted_specialties"] == [
        "dental",
        "dentist",
        "dentistry",
        "stomatology",
    ]

    # Услуга без department_key - проверка неприменима (None, не []).
    plain_row = rows[plain_service.id]
    assert plain_row["department_key"] is None
    assert plain_row["accepted_specialties"] is None


@pytest.mark.integration
def test_registrar_services_eligibility_mirrors_gate_source_not_link(
    client,
    db_session,
    admin_user,
    admin_password,
):
    """Codex P1 #3311: accepted_specialties считаются от ТОГО ЖЕ источника,
    что и гейт корзины (поле Service.department_key), а не от link-priority
    service_data['department_key'] (DepartmentService-связь).

    При расхождении связи и поля: payload.department_key = ключ связи
    ('cardiology' — им же группируется вкладка), а accepted_specialties =
    dental-семейство поля 'dental' — иначе UI предложит врача, которого
    POST /registrar/cart отклонит гейтом RQ-05.a.
    """
    from app.models.department import Department, DepartmentService

    cardio_department = Department(
        key="cardiology",
        name_ru="Кардиология (link)",
        name_uz="Kardiologiya",
        active=True,
    )
    db_session.add(cardio_department)
    db_session.commit()
    db_session.refresh(cardio_department)

    divergent_service = Service(
        name="RQ-08a Расходящаяся услуга",
        code="D89a",
        service_code="D89a",
        category_code="S",
        department_key="dental",  # поле — источник гейта корзины
        price=Decimal("10000.00"),
        currency="UZS",
        duration_minutes=30,
        active=True,
    )
    db_session.add(divergent_service)
    db_session.commit()
    db_session.refresh(divergent_service)

    db_session.add(
        DepartmentService(
            department_id=cardio_department.id,
            service_id=divergent_service.id,
        )
    )
    db_session.commit()

    from tests.conftest import mint_access_token

    headers = {"Authorization": f"Bearer {mint_access_token(admin_user)}"}
    response = client.get("/api/v1/registrar/services", headers=headers)

    assert response.status_code == 200, response.text
    payload = response.json()["services_by_group"]
    rows = {
        row["id"]: row
        for group_rows in payload.values()
        for row in group_rows
    }

    row = rows[divergent_service.id]
    # Группировка/отображение — по связи (link-priority), как раньше.
    assert row["department_key"] == "cardiology"
    # Eligibility — зеркало гейта: от ПОЛЯ услуги, не от связи.
    assert row["accepted_specialties"] == [
        "dental",
        "dentist",
        "dentistry",
        "stomatology",
    ]


@pytest.mark.integration
def test_registrar_services_null_field_with_link_keeps_gate_no_check_semantics(
    client,
    db_session,
    admin_user,
    admin_password,
):
    """Codex P1 #3311 (раунд 2): пустое поле Service.department_key + связь
    DepartmentService (add_service_to_department не обновляет поле).

    Гейт RQ-05.a при service.department_key=None специальность НЕ проверяет
    (accepted is None). Сериализатор обязан отдать accepted_specialties=None
    (явное «проверка неприменима»), а не набор от link-ключа — фронт по null
    показывает всех врачей, зеркаля гейт.
    """
    from app.models.department import Department, DepartmentService

    cardio_department = Department(
        key="cardiology",
        name_ru="Кардиология (link 2)",
        name_uz="Kardiologiya",
        active=True,
    )
    db_session.add(cardio_department)
    db_session.commit()
    db_session.refresh(cardio_department)

    no_field_service = Service(
        name="RQ-08a Услуга без поля со связью",
        code="P90a",
        service_code="P90a",
        category_code="O",
        # department_key НЕ задан (None) — источник гейта пуст
        price=Decimal("5000.00"),
        currency="UZS",
        duration_minutes=30,
        active=True,
    )
    db_session.add(no_field_service)
    db_session.commit()
    db_session.refresh(no_field_service)

    db_session.add(
        DepartmentService(
            department_id=cardio_department.id,
            service_id=no_field_service.id,
        )
    )
    db_session.commit()

    from tests.conftest import mint_access_token

    headers = {"Authorization": f"Bearer {mint_access_token(admin_user)}"}
    response = client.get("/api/v1/registrar/services", headers=headers)

    assert response.status_code == 200, response.text
    payload = response.json()["services_by_group"]
    rows = {
        row["id"]: row
        for group_rows in payload.values()
        for row in group_rows
    }

    row = rows[no_field_service.id]
    # Отображение — по связи (link-priority), как раньше.
    assert row["department_key"] == "cardiology"
    # Eligibility — ЯВНЫЙ null (не набор от link-ключа): гейт не проверяет.
    assert row["accepted_specialties"] is None
