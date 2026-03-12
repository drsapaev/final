# AI Skills Trust Review

Date: 2026-03-06

## Review Method

Level 1 automated scan:

- Scanner: `C:/final/.codex/skills/aif-skill-generator/scripts/security-scan.py`

Level 2 semantic review:

- Manual review of each selected skill's purpose and whether instructions stay aligned with that purpose

## Review Scope

Reviewed for this foundation:

- 12 new local custom skills added under `.codex/skills/`
- 7 pre-existing external reference skills already present under `.agents/skills/`

No new external skill installation was performed during this setup.

## Result Summary

| Group | Count | Level 1 result | Level 2 result | Decision |
|---|---|---|---|---|
| New local custom skills | 12 | All exit code `0` | Purpose-aligned, narrow, no unrelated instructions found | approved |
| External reference skills | 5 | Exit code `0` | Purpose-aligned | approved as reference-only |
| External reference skills with warnings | 2 | Exit code `2` | Warnings were limited to package-install examples; no unrelated or manipulative instructions found | approved as reference-only with caution |

## Local Custom Skills

All local custom skills scanned clean and passed manual review:

- `repo-audit`
- `docs-vs-code-verification`
- `service-repository-refactor`
- `ci-cd-stabilization`
- `auth-rbac-audit`
- `frontend-backend-contract-audit`
- `queue-consistency-audit`
- `payment-hardening`
- `accessibility-polish`
- `security-housekeeping`
- `critical-flow-test-mapping`
- `docs-cleanup`

Review notes:

- no network exfiltration instructions
- no secret-access instructions
- no destructive shell guidance
- no hidden approval-bypass behavior
- each skill is scoped to one task class and points back to repo guardrails

## External Reference Skills

| Skill | Level 1 | Level 2 note | Trust decision |
|---|---|---|---|
| `fastapi-templates` | clean (`0`) | Purpose matches backend pattern guidance | reference-only approved |
| `github-actions-templates` | clean (`0`) | Purpose matches workflow templating; still not authority for permission changes | reference-only approved |
| `vite` | clean (`0`) | Purpose matches Vite config guidance | reference-only approved |
| `vitest` | clean (`0`) | Purpose matches Vitest guidance | reference-only approved |
| `webapp-testing` | clean (`0`) | Purpose matches browser-testing guidance | reference-only approved |
| `python-testing-patterns` | warnings (`2`) | Warnings came from `pip install` examples in docs; manual review found no unrelated instructions | reference-only approved with caution |
| `vercel-react-best-practices` | warnings (`2`) | Warning came from an `npm install` example in docs; manual review found no unrelated instructions | reference-only approved with caution |

## Trust Policy For Actual Use

Approved does not mean unconstrained.

All skills in this repo remain subject to:

- `docs/status/AI_AUTOMATION_GUARDRAILS.md`
- `.ai-factory/contracts/*.json`
- human review for protected zones

Additional rules:

- external skills are advisory references only
- local custom skills may guide planning and bounded execution but do not override repo guardrails
- any future external skill install must be scanned before use

## Residual Risk

- External reference skills can still drift over time if reinstalled from upstream.
- Warnings in `python-testing-patterns` and `vercel-react-best-practices` were benign in this review, but they should be re-scanned if updated.
- Broader pre-existing global skills outside this review are not automatically trusted for this execution framework.
