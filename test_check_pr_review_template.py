import unittest

from scripts.check_pr_review_template import validate_pr_body


VALID_DOCS_ONLY_BODY = """
## Summary

- Add docs-only PR review process gate.
- No runtime behavior changed.

## Cyclic Execution Evidence

- Fresh main sync: branch created from current origin/main
- Clean workspace: inspected before edits; only docs/process files changed
- Branch: docs/pr-review-process-gate
- Scope gate: allowed docs/runbooks/** and checker files; denied runtime
- Red-check handling: fix any failed PR gate in this same PR before merge

## Contract Impact

not applicable - docs/process only, no API or frontend consumer contract changed.

## RBAC / Permissions

not applicable - no route, endpoint, guard, or auth-sensitive behavior changed.

## Notification / Realtime

not applicable - no event, websocket, chat, or realtime behavior changed.

## Frontend Resilience

not applicable - no user-facing panel or frontend data flow changed.

## Scope Gate

- Allowed paths: docs/runbooks/**
- Denied paths: backend runtime, frontend runtime, migrations
- Migration/docs/test impact: docs only
- Rollback note: revert the docs changes

## Validation

- Targeted tests or smoke run: PR body gate script
- Result: passed
- Not checked: runtime app behavior
"""


VALID_RUNTIME_BODY = """
## Summary

- Add a registrar service payload mapping regression.
- Keep legacy aliases documented.

## Cyclic Execution Evidence

- Fresh main sync: branch created from current origin/main
- Clean workspace: inspected before edits; only scoped endpoint, consumer, and tests changed
- Branch: fix/registrar-services-contract
- Scope gate: allowed registrar endpoint, consumer, and targeted tests; denied unrelated panels and migrations
- Red-check handling: fix any failed targeted test or CI check in this same PR before merge

## Contract Impact

- Canonical surface: GET /api/v1/registrar/services
- Request shape: authenticated request, no body
- Response shape: grouped service dictionary
- Status codes: 200, 401, 403
- Frontend consumer: registrar service selector
- Compatibility path or alias: legacy code-prefix fallback remains compatibility only
- Contract proof: backend contract test and frontend consumer test

## RBAC / Permissions

- Roles allowed: registrar, admin
- Roles denied: doctor, patient
- Positive auth proof: registrar token returns 200
- Negative auth proof: patient token returns 403

## Notification / Realtime

not applicable - no event, websocket, chat, or realtime behavior changed.

## Frontend Resilience

- Empty data proof: empty group renders empty selector state
- Partial data proof: missing optional description does not crash
- Forbidden secondary path behavior: not applicable, no secondary path used
- Missing draft/resource behavior: not applicable, no draft/resource path changed
- Stale route/deep-link behavior: not applicable, no route state changed

## Scope Gate

- Allowed paths: backend registrar endpoint, frontend registrar consumer, targeted tests
- Denied paths: unrelated admin panels, migrations
- Migration/docs/test impact: no migration; targeted tests added
- Rollback note: revert endpoint and consumer changes

## Validation

- Targeted tests or smoke run: pytest targeted backend/frontend regression tests
- Result: passed
- Not checked: full browser panel smoke
"""


class PRReviewTemplateValidationTests(unittest.TestCase):
    def test_rejects_empty_body(self):
        result = validate_pr_body("")

        self.assertEqual(
            result.errors,
            ["PR body is empty. Fill the review quality gate template."],
        )

    def test_rejects_missing_required_section(self):
        body = VALID_DOCS_ONLY_BODY.replace("## Validation", "## Evidence")

        result = validate_pr_body(body)

        self.assertIn("Missing required section: ## Validation", result.errors)

    def test_rejects_unfilled_template_placeholders(self):
        body = """
## Summary

Describe the change in 2-4 bullets.

## Cyclic Execution Evidence

- Fresh main sync:

## Contract Impact

- Canonical surface:

## RBAC / Permissions

- Roles allowed:

## Notification / Realtime

- Event type or websocket channel:

## Frontend Resilience

- Empty data proof:

## Scope Gate

- Allowed paths:

## Validation

- Targeted tests or smoke run:
"""

        result = validate_pr_body(body)

        self.assertEqual(len(result.errors), 8)
        self.assertTrue(any("## Contract Impact" in error for error in result.errors))

    def test_rejects_missing_cyclic_execution_evidence(self):
        body = VALID_DOCS_ONLY_BODY.replace("## Cyclic Execution Evidence", "## Cycle")

        result = validate_pr_body(body)

        self.assertIn("Missing required section: ## Cyclic Execution Evidence", result.errors)

    def test_rejects_partial_cyclic_execution_evidence(self):
        body = VALID_DOCS_ONLY_BODY.replace(
            "- Clean workspace: inspected before edits; only docs/process files changed",
            "- Clean workspace:",
        )

        result = validate_pr_body(body)

        self.assertTrue(any("## Cyclic Execution Evidence" in error for error in result.errors))
        self.assertTrue(any("Clean workspace" in error for error in result.errors))

    def test_html_comments_do_not_count_as_section_answers(self):
        body = VALID_DOCS_ONLY_BODY.replace(
            "- Add docs-only PR review process gate.\n- No runtime behavior changed.",
            "<!-- Author guidance only; this is not an answer. -->",
        )

        result = validate_pr_body(body)

        self.assertTrue(any("## Summary" in error for error in result.errors))

    def test_accepts_body_with_utf8_bom_prefix(self):
        result = validate_pr_body("\ufeff" + VALID_DOCS_ONLY_BODY)

        self.assertEqual(result.errors, [])

    def test_rejects_partially_filled_required_fields(self):
        body = """
## Summary

- Add a partially documented runtime change.

## Contract Impact

- Canonical surface: GET /api/v1/example
- Request shape:
- Response shape:
- Status codes:
- Frontend consumer:
- Compatibility path or alias:
- Contract proof:

## RBAC / Permissions

not applicable - no route, endpoint, guard, or auth-sensitive behavior changed.

## Notification / Realtime

not applicable - no event, websocket, chat, or realtime behavior changed.

## Frontend Resilience

not applicable - no user-facing panel or frontend data flow changed.

## Scope Gate

- Allowed paths: backend/app/api/example.py
- Denied paths:
- Migration/docs/test impact:
- Rollback note:

## Validation

- Targeted tests or smoke run: validator smoke
- Result: passed
- Not checked: runtime app behavior
"""

        result = validate_pr_body(body)

        self.assertTrue(any("## Contract Impact" in error for error in result.errors))
        self.assertTrue(any("Request shape" in error for error in result.errors))
        self.assertTrue(any("## Scope Gate" in error for error in result.errors))
        self.assertTrue(any("Denied paths" in error for error in result.errors))

    def test_rejects_not_applicable_without_specific_reason(self):
        body = VALID_DOCS_ONLY_BODY.replace(
            "not applicable - docs/process only, no API or frontend consumer contract changed.",
            "not applicable",
        )

        result = validate_pr_body(body)

        self.assertTrue(any("## Contract Impact" in error for error in result.errors))

    def test_field_level_not_applicable_does_not_fill_entire_section(self):
        body = VALID_RUNTIME_BODY.replace(
            "- Partial data proof: missing optional description does not crash",
            "- Partial data proof:",
        )

        result = validate_pr_body(body)

        self.assertTrue(any("## Frontend Resilience" in error for error in result.errors))
        self.assertTrue(any("Partial data proof" in error for error in result.errors))

    def test_accepts_docs_only_body_with_specific_not_applicable_reasons(self):
        result = validate_pr_body(VALID_DOCS_ONLY_BODY)

        self.assertEqual(result.errors, [])
        self.assertEqual(
            result.warnings,
            [
                "`not applicable` is accepted, but reviewers should confirm the reason is specific."
            ],
        )

    def test_accepts_runtime_body_with_review_proof_fields(self):
        result = validate_pr_body(VALID_RUNTIME_BODY)

        self.assertEqual(result.errors, [])


if __name__ == "__main__":
    unittest.main()
