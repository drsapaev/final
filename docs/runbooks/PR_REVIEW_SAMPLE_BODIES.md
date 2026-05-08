# PR Review Sample Bodies

Use these examples when filling `.github/pull_request_template.md` or when testing the local PR review gate.

The sample files are intentionally valid PR bodies, not explanatory docs. You can pass them directly to the checker:

```powershell
python scripts/run_pr_review_gate_checks.py
python scripts/check_pr_review_template.py --body-file docs\runbooks\pr-review-samples\docs-only-pr.md
python scripts/check_pr_review_template.py --body-file docs\runbooks\pr-review-samples\runtime-contract-pr.md
```

The dedicated PR gate workflow runs `scripts/run_pr_review_gate_checks.py`, which also validates these samples. A future checker/template change must keep the examples current.

## Docs-Only Or Process PR

Use `docs/runbooks/pr-review-samples/docs-only-pr.md` when the PR changes only documentation, templates, or process files.

Expected pattern:
- Runtime sections use `not applicable` with a specific reason.
- Scope Gate names allowed and denied paths.
- Validation explains what was checked and what was intentionally not checked.

## Runtime Contract PR

Use `docs/runbooks/pr-review-samples/runtime-contract-pr.md` when the PR changes an endpoint, payload shape, frontend consumer, or role-sensitive surface.

Expected pattern:
- Contract Impact names the canonical surface and frontend consumer.
- RBAC / Permissions includes positive and negative auth proof.
- Frontend Resilience states empty, partial, and fallback behavior.
- Validation names targeted tests or smoke proof.

## Reviewer Use

When a PR body is unclear, compare it to the closest sample:

- If the PR is docs-only, it should look like the docs-only sample and avoid runtime proof.
- If the PR changes runtime behavior, it should look like the runtime contract sample and include proof fields.
- If the PR is risky but neither sample fits, keep the template sections and fill each one with the closest concrete proof.
