# PR Review Adoption Log

Use this log with `docs/runbooks/PR_REVIEW_PRACTICE_TRACK.md`.

This is not a release gate. It is a lightweight weekly record of what the team practiced, what repeated, and what should become a rule, test, or checklist improvement.

## How To Use

- Add one entry per week or per reviewed risky PR.
- Keep entries factual and short.
- Link the PR, branch, or local evidence when available.
- Record `none` when no gap was observed.
- If the same gap repeats twice, propose a candidate project rule instead of growing the checklist.

Helper command:

```powershell
python scripts/add_pr_review_adoption_entry.py `
  --focus "PR #123 registrar services" `
  --track "Contract / RBAC" `
  --evidence "PR body, diff, targeted tests" `
  --gate-result passed `
  --gap "none" `
  --prevention "targeted contract proof added" `
  --next-action "watch next registrar API PR"
```

Add `--write` only after reviewing the generated entry. The helper inserts new entries at the top of the `Log` section.

## Entry Template

```markdown
## YYYY-MM-DD - <PR or focus>

- Track: Contract / RBAC / Notification / Realtime / Frontend resilience / Scope / Release readiness
- Evidence reviewed: <PR link, branch, runbook, smoke log, or diff>
- Gate result: passed / failed / partial / not run
- Repeated gap observed: <specific gap or none>
- Prevention added: <test, checklist, doc, workflow, or none>
- Next action: <smallest next step>
```

## Metrics Snapshot

| Metric | Current count | Notes |
|---|---:|---|
| Contract drift caught during review | 0 | Start counting when the gate is applied to live PRs. |
| RBAC issue caught before merge | 0 | Count endpoint or route-surface permission gaps. |
| Realtime/read-state drift caught before merge | 0 | Count websocket/read/unread convergence gaps. |
| PR scope issue caught before merge | 0 | Count unrelated files or unclear allowed path sets. |
| CI/env repeat caught before merge | 0 | Count lockfile, port, Postgres/SQLite, CORS, or migration drift. |

## Log

## 2026-05-02 - PR #83 registrar wizard duplicate gate

- Track: Contract / Scope gate adoption
- Evidence reviewed: PR body updated via authenticated gh with Contract Impact, RBAC / Permissions, Notification / Realtime, Frontend Resilience, Scope Gate, and Validation sections
- Gate result: passed
- Repeated gap observed: older runtime-risk duplicate gate PR body had Summary and Testing only
- Prevention added: PR #83 now documents duplicate-claim contract, active statuses, RBAC non-impact, scope, rollback, and validation proof
- Next action: Continue high-risk bodies with PR #80 and PR #79
## 2026-05-02 - PR #85 wizard allocator seam extraction

- Track: Contract / Scope gate adoption
- Evidence reviewed: PR body updated via authenticated gh with Contract Impact, RBAC / Permissions, Notification / Realtime, Frontend Resilience, Scope Gate, and Validation sections
- Gate result: passed
- Repeated gap observed: older runtime-risk wizard seam PR body had Summary and Testing only
- Prevention added: PR #85 now documents wizard seam contract, RBAC non-impact, scope, rollback, and validation proof
- Next action: Continue high-risk bodies with PR #83
## 2026-05-02 - PR #88 wizard create-branch handoff extraction

- Track: Contract / Scope gate adoption
- Evidence reviewed: PR body updated via authenticated gh with Contract Impact, RBAC / Permissions, Notification / Realtime, Frontend Resilience, Scope Gate, and Validation sections
- Gate result: passed
- Repeated gap observed: older runtime-risk wizard extraction PR body had Summary and Validation only
- Prevention added: PR #88 now documents extracted handoff contract, RBAC non-impact, scope, rollback, and validation proof
- Next action: Continue high-risk bodies with PR #85 and PR #83
## 2026-05-02 - Open PR body gate sweep

- Track: PR Scope And Release Readiness
- Evidence reviewed: Unauthenticated GitHub REST sweep over 43 open PR bodies using validate_pr_body
- Gate result: partial
- Repeated gap observed: 5 open PR bodies passed (#93,#92,#91,#90,#89); 38 still miss required quality gate sections
- Prevention added: Sweep identifies remaining old-format PRs before review/merge
- Next action: Prioritize #88, #85, #83, #80, #79, #74, #70, #66, #65, #64, #63 as runtime-risk bodies
## 2026-05-02 - PR #89 wizard boundary readiness recheck

- Track: Scope gate adoption
- Evidence reviewed: PR body updated on GitHub with docs-only gate sections and explicit no-impact reasons
- Gate result: passed
- Repeated gap observed: older docs-only readiness PR body had Summary and Validation only
- Prevention added: PR #89 now documents no contract/RBAC/runtime impact and docs-only allowed scope
- Next action: Run open PR gate sweep to find any remaining body gaps
## 2026-05-02 - PR #91 registrar allocator follow-up inventory

- Track: Scope gate adoption
- Evidence reviewed: PR body updated on GitHub with docs-only gate sections and explicit no-impact reasons
- Gate result: passed
- Repeated gap observed: older docs-only PR body had Summary and Notes only
- Prevention added: PR #91 now documents no contract/RBAC/runtime impact and docs-only allowed scope
- Next action: Consider PR #89 docs-only readiness body next
## 2026-05-02 - PR #92 registrar batch create-action characterization

- Track: Contract / Scope gate adoption
- Evidence reviewed: PR body updated on GitHub with gate sections and explicit characterization-only not-applicable reasons
- Gate result: passed
- Repeated gap observed: older characterization PR body had Summary and Notes only
- Prevention added: PR #92 now documents no contract/RBAC/runtime impact and allowed docs/test scope
- Next action: Apply docs-only gate body to PR #91
## 2026-05-02 - PR #90 Wave 2C wizard seam migration

- Track: Contract / RBAC / Scope gate adoption
- Evidence reviewed: PR body updated on GitHub with Contract Impact, RBAC / Permissions, Notification / Realtime, Frontend Resilience, Scope Gate, and Validation sections
- Gate result: passed
- Repeated gap observed: older risky queue allocator PR body had Summary and Validation only
- Prevention added: PR #90 now carries explicit queue allocator contract, RBAC non-impact, scope, rollback, and validation proof
- Next action: Apply lighter docs/test-only gate bodies to PR #92 and PR #91
## 2026-05-02 - PR #93 fix: restore registrar batch create-action path

- Track: Contract / RBAC / Scope gate adoption
- Evidence reviewed: PR body updated on GitHub with Contract Impact, RBAC / Permissions, Notification / Realtime, Frontend Resilience, Scope Gate, and Validation sections
- Gate result: passed
- Repeated gap observed: older PR body was missing the required review gate sections
- Prevention added: PR #93 now carries explicit contract, RBAC non-impact, scope, rollback, and validation proof
- Next action: Use the same template on the next open risky registrar/queue PR
## 2026-05-02 - PR #93 fix: restore registrar batch create-action path

- Track: Contract / RBAC / Scope gate adoption
- Evidence reviewed: Real PR body from https://github.com/drsapaev/final/pull/93; runner passed internal checks but failed live PR body
- Gate result: failed
- Repeated gap observed: PR body only has Summary and Testing; missing Contract Impact, RBAC / Permissions, Notification / Realtime, Frontend Resilience, Scope Gate, and Validation sections
- Prevention added: Gate blocks review without explicit contract/auth/scope proof for risky registrar queue path
- Next action: Update PR #93 body with required gate sections or mark specific not-applicable reasons
## 2026-05-02 - PR review quality gate workflow checkout

- Track: PR Scope And Release Readiness
- Evidence reviewed: Workflow reviewed; base SHA checkout replaced with PR code checkout; gate runner passed
- Gate result: passed
- Repeated gap observed: CI could validate stale base-branch gate code instead of PR-side runner/tests
- Prevention added: Workflow now checks out PR code before running gate
- Next action: Apply gate to next real PR body
## 2026-05-02 - PR review gate bootstrap

- Track: Scope / Release readiness
- Evidence reviewed: local docs/process implementation of PR review gate, samples, checker, tests, and workflow.
- Gate result: passed locally via `python scripts/run_pr_review_gate_checks.py --body-file docs/runbooks/pr-review-samples/runtime-contract-pr.md`.
- Repeated gap observed: weak `not applicable` fields in a runtime sample were caught by the checker before documentation was finalized.
- Prevention added: checker field validation, sample PR bodies, unit tests, unified local/CI runner, and hidden PR template guidance.
- Next action: apply the runner to a real PR body or diff and record the first live adoption entry.
