from types import SimpleNamespace

from app.services.queue_admin_directions_read_service import _allowed_actions


def test_parent_conflict_review_action_targets_the_queue_profile():
    profile = SimpleNamespace(
        id=41,
        key="aqs-synthetic-profile",
        department_key="aqs-explicit-parent",
        is_active=True,
        show_on_qr_page=False,
    )
    availability = SimpleNamespace(
        state="conflict",
        reason_codes=("parent_conflict",),
        parent_department_key=None,
    )

    actions = _allowed_actions(
        profile,
        availability,
        mode="booking",
        public_available=False,
        publish_candidate_available=False,
        has_address=False,
    )

    assert [action.model_dump() for action in actions] == [
        {
            "kind": "review_configuration",
            "entity_type": "queue_profile",
            "entity_id": 41,
            "entity_key": "aqs-synthetic-profile",
        }
    ]


def test_inactive_parent_review_action_remains_department_scoped():
    profile = SimpleNamespace(
        id=42,
        key="aqs-synthetic-profile",
        department_key="aqs-inactive-parent",
        is_active=True,
        show_on_qr_page=False,
    )
    availability = SimpleNamespace(
        state="unavailable",
        reason_codes=("parent_inactive",),
        parent_department_key="aqs-inactive-parent",
    )

    actions = _allowed_actions(
        profile,
        availability,
        mode="booking",
        public_available=False,
        publish_candidate_available=False,
        has_address=False,
    )

    assert [action.model_dump() for action in actions] == [
        {
            "kind": "review_configuration",
            "entity_type": "department",
            "entity_id": None,
            "entity_key": "aqs-inactive-parent",
        }
    ]
