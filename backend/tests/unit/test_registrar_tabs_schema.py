"""Validation of the internal Registrar tab registry command."""

import pytest
from pydantic import ValidationError

from app.schemas.registrar_tabs import RegistrarTabInput, RegistrarTabsUpdate


def _payload(tabs=None, **overrides):
    return {
        "expected_version": 0,
        "tabs": tabs or [],
        "reason": "configure_registrar_tabs",
        **overrides,
    }


@pytest.mark.parametrize("target_id", [0, -1, True, "1"])
def test_target_identity_requires_a_positive_integer(target_id):
    with pytest.raises(ValidationError):
        RegistrarTabInput(target_kind="doctor", target_id=target_id)


def test_duplicate_typed_target_is_rejected_but_axes_may_share_numeric_id():
    with pytest.raises(ValidationError):
        RegistrarTabsUpdate.model_validate(
            _payload(
                [
                    {"target_kind": "doctor", "target_id": 1},
                    {"target_kind": "doctor", "target_id": 1},
                ]
            )
        )
    accepted = RegistrarTabsUpdate.model_validate(
        _payload(
            [
                {"target_kind": "profile", "target_id": 1},
                {"target_kind": "doctor", "target_id": 1},
            ]
        )
    )
    assert len(accepted.tabs) == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"expected_version": -1},
        {"expected_version": True},
        {"reason": "other"},
        {"extra": True},
    ],
)
def test_command_rejects_invalid_version_reason_or_unknown_fields(overrides):
    with pytest.raises(ValidationError):
        RegistrarTabsUpdate.model_validate(_payload(**overrides))


def test_saved_empty_list_is_explicit_and_not_replaced_by_defaults():
    command = RegistrarTabsUpdate.model_validate(_payload())
    assert command.tabs == []
    assert command.expected_version == 0


def test_title_normalization_and_control_character_rejection():
    tab = RegistrarTabInput(
        target_kind="profile", target_id=1, title="  SYNTHETIC label  "
    )
    assert tab.title == "SYNTHETIC label"
    assert (
        RegistrarTabInput(target_kind="doctor", target_id=1, title="  ").title is None
    )
    with pytest.raises(ValidationError):
        RegistrarTabInput(target_kind="doctor", target_id=1, title="invalid\nlabel")


def test_tab_limit_and_unknown_target_kind_are_rejected():
    with pytest.raises(ValidationError):
        RegistrarTabsUpdate.model_validate(
            _payload(
                [
                    {"target_kind": "doctor", "target_id": number}
                    for number in range(1, 202)
                ]
            )
        )
    with pytest.raises(ValidationError):
        RegistrarTabInput(target_kind="resource", target_id=1)


def test_visibility_requires_boolean_and_target_fields_are_closed():
    with pytest.raises(ValidationError):
        RegistrarTabInput(target_kind="profile", target_id=1, visible="false")
    with pytest.raises(ValidationError):
        RegistrarTabInput(target_kind="profile", target_id=1, queue_tags=["synthetic"])
