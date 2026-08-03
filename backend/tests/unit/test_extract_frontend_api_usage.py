"""Unit tests for extract_frontend_api_usage.py.

Covers the TypeScript generic-argument fix (PR follow-up to #2672):
`api.get<UserDto>(...)` must be matched the same as `api.get(...)`.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module():
    root = Path(__file__).resolve().parents[3]
    script_path = root / "ops" / "scripts" / "extract_frontend_api_usage.py"
    spec = importlib.util.spec_from_file_location("extract_frontend_api_usage", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load extract_frontend_api_usage.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def extractor():
    return _load_module()


@pytest.mark.unit
class TestAxiosMethodCallPattern:
    """Verify AXIOS_METHOD_CALL_PATTERN handles TypeScript generics."""

    def test_plain_call_without_generic(self, extractor):
        """`api.get('/url')` must still match (no regression)."""
        content = "api.get('/patients/1')"
        matches = list(extractor.AXIOS_METHOD_CALL_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group("method").lower() == "get"

    def test_typed_call_with_generic(self, extractor):
        """`api.get<UserDto>('/url')` must match — the bug fixed in this PR."""
        content = "api.get<UserDto>('/auth/me')"
        matches = list(extractor.AXIOS_METHOD_CALL_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group("method").lower() == "get"

    def test_typed_post_with_generic(self, extractor):
        """`api.post<VisitDto>(...)` must match."""
        content = "api.post<VisitDto>('/visits', payload)"
        matches = list(extractor.AXIOS_METHOD_CALL_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group("method").lower() == "post"

    def test_typed_put_with_generic(self, extractor):
        """`api.put<PatientDto>(...)` must match."""
        content = "api.put<PatientDto>(`/patients/${id}`, body)"
        matches = list(extractor.AXIOS_METHOD_CALL_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group("method").lower() == "put"

    def test_typed_delete_with_generic(self, extractor):
        """`api.delete<void>(...)` must match."""
        content = "api.delete<void>('/items/1')"
        matches = list(extractor.AXIOS_METHOD_CALL_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group("method").lower() == "delete"

    def test_typed_call_with_whitespace_before_generic(self, extractor):
        """`api.get <UserDto>(...)` (rare but legal TS) must match."""
        content = "api.get <UserDto>('/url')"
        matches = list(extractor.AXIOS_METHOD_CALL_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group("method").lower() == "get"

    def test_typed_call_with_whitespace_after_generic(self, extractor):
        """`api.get<UserDto> ('/url')` must match."""
        content = "api.get<UserDto> ('/url')"
        matches = list(extractor.AXIOS_METHOD_CALL_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group("method").lower() == "get"

    def test_all_six_methods_match_with_generic(self, extractor):
        """Every method in the alternation must match with a generic arg."""
        for method in ("get", "post", "put", "patch", "delete", "options", "head"):
            content = f"api.{method}<T>('/url')"
            matches = list(extractor.AXIOS_METHOD_CALL_PATTERN.finditer(content))
            assert len(matches) == 1, f"method={method!r} did not match"
            assert matches[0].group("method").lower() == method

    def test_non_api_method_not_matched(self, extractor):
        """`myapi.get(...)`, `apiget(...)` must not match (word boundary)."""
        for content in ("myapi.get('/url')", "apiget('/url')", "api.getx('/url')"):
            matches = list(extractor.AXIOS_METHOD_CALL_PATTERN.finditer(content))
            assert matches == [], f"unexpected match in {content!r}"


@pytest.mark.unit
class TestCollectFrontendCallsIntegration:
    """End-to-end test: collect_frontend_calls on a fake frontend tree."""

    def test_typed_and_untyped_calls_collected_equally(self, extractor, tmp_path):
        """A mixed file with both `api.get(...)` and `api.get<T>(...)` must
        produce 2 ApiCall entries, one per call, both with method='GET'.
        """
        frontend_root = tmp_path / "frontend" / "src"
        (frontend_root / "api").mkdir(parents=True)
        (frontend_root / "api" / "mixed.ts").write_text(
            "export const fetchPlain = () => api.get('/plain');\n"
            "export const fetchTyped = () => api.get<UserDto>('/typed');\n"
            "export const createTyped = () => api.post<VisitDto>('/visits', body);\n",
            encoding="utf-8",
        )

        calls = extractor.collect_frontend_calls(frontend_root)

        # 3 calls total: 1 plain + 2 typed
        assert len(calls) == 3, f"expected 3 calls, got {len(calls)}: {calls}"
        methods = sorted(c.method for c in calls)
        assert methods == ["GET", "GET", "POST"], methods
        # Verify the typed calls' endpoint literals are extracted correctly
        endpoints = sorted(c.endpoint_literal for c in calls if c.endpoint_literal)
        assert endpoints == ["/plain", "/typed", "/visits"], endpoints

    def test_visits_ts_pattern_matched(self, extractor, tmp_path):
        """Reproduces the exact pattern from frontend/src/api/visits.ts that
        was silently skipped before the fix.
        """
        frontend_root = tmp_path / "frontend" / "src"
        (frontend_root / "api").mkdir(parents=True)
        (frontend_root / "api" / "visits.ts").write_text(
            "import { api } from './client';\n"
            "import type { VisitDto, VisitWithServicesDto } from '../types';\n\n"
            "export const getVisit = (id: string) =>\n"
            "  api.get<VisitWithServicesDto>(`/visits/visits/${encodeURIComponent(id)}`);\n\n"
            "export const createVisit = (data: unknown) =>\n"
            "  api.post<VisitDto>('/visits', data);\n",
            encoding="utf-8",
        )

        calls = extractor.collect_frontend_calls(frontend_root)

        assert len(calls) == 2, f"expected 2 calls, got {len(calls)}"
        # Both should be matched (was 0 before the fix)
        methods = sorted(c.method for c in calls)
        assert methods == ["GET", "POST"], methods
