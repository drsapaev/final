from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.parametrize(
    ("path", "expected_key"),
    [
        ("/api/v1/specialized/dentistry/patients", "patients"),
        ("/api/v1/specialized/dentistry/visits", "visits"),
        ("/api/v1/specialized/cardiology/patients", "patients"),
        ("/api/v1/specialized/cardiology/visits", "visits"),
    ],
)
def test_specialized_panel_endpoints_accept_list_role_dependencies(
    client,
    auth_headers,
    path: str,
    expected_key: str,
):
    response = client.get(path, headers=auth_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert expected_key in body
