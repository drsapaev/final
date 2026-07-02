from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.feature_flags_api_service import (
    FeatureFlagsApiDomainError,
    FeatureFlagsApiService,
)


@pytest.mark.unit
class TestFeatureFlagsApiService:
    def test_get_flag_or_error_raises_for_missing(self):
        repository = SimpleNamespace(get_by_key=lambda flag_key: None)
        service = FeatureFlagsApiService(
            db=None,
            repository=repository,
            feature_service=SimpleNamespace(),
        )

        with pytest.raises(FeatureFlagsApiDomainError) as exc_info:
            service.get_flag_or_error("missing")

        assert exc_info.value.status_code == 404

    def test_create_flag_checks_uniqueness_and_calls_feature_service(self):
        repository = SimpleNamespace(exists=lambda flag_key: False)
        created = SimpleNamespace(key="new_flag")
        feature_service = SimpleNamespace(
            create_flag=lambda **kwargs: created,
        )
        service = FeatureFlagsApiService(
            db=None,
            repository=repository,
            feature_service=feature_service,
        )

        result = service.create_flag(
            key="new_flag",
            name="Name",
            description=None,
            enabled=True,
            config={},
            category="general",
            environment="all",
            user_id="admin",
        )

        assert result.key == "new_flag"

