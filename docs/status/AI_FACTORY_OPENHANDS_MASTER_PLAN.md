# AI Factory + OpenHands Master Plan

Date: 2026-03-06

## Current State

- Control plane foundation exists (`.ai-factory`, custom skills, contract templates, guardrails docs).
- OpenHands integration is contract-driven and partial; no claim of full automatic bridge.
- Latest `main` CI truth is mixed:
  - failed unified runs on `main`: `22748643145`, `22717403048`
  - latest known green unified run on `main`: `22701910411`
- Primary blocker on failed `main` runs: frontend test suite (`TwoFactorManager` mock/export mismatch).
- PR backlog remains large and overlapping (`30` open PRs).

## Target Architecture

- AI Factory: planner, policy, memory, skills, contract authoring.
- OpenHands: bounded executor in workspace with strict task contracts.
- GitHub Actions: independent arbiter.
- Human: final approver for protected domains and merge decisions.

## Integration Strategy

- PR-first, bounded execution by task contract.
- Small scoped tasks with mandatory evidence.
- Protected zones (auth/payment/queue/EMR/migrations/secrets/workflow permissions) require escalation and human review.
- Honest status labels: `done`, `partial`, `blocked`, `pending human review`.

## Risks

- CI signal instability on `main` while frontend blocker remains unresolved.
- Docs/reports drift from current runtime/CI reality.
- Security debt in dependencies and static findings.
- Auth audit commands include environment-dependent scripts that can fail non-deterministically.

## Priorities

Wave 1 order (revalidated by evidence):

1. `W1-T1` CI/CD truth matrix
2. `W1-T2` docs vs code ground truth
3. `W1-T3` auth/RBAC audit
4. `W1-T4` security housekeeping

Reason for order: docs-truth and RBAC decisions depend on a fresh CI evidence baseline.

## Waves

| Wave | Goal | Gate |
|---|---|---|
| Stabilization | CI truth, docs ground truth, RBAC/security baseline | Evidence complete for W1 tasks |
| Structural hardening | Protected-domain remediation slices | Human review for protected changes |
| Polish | UX/docs cleanup after structural risks are explicit | No unresolved critical blockers |

## Stop/Go Gates

- Stop immediately if task crosses contract scope.
- Stop if protected paths are touched unexpectedly.
- Stop if required checks cannot run and no reproducible fallback exists.
- Go to next wave only after Wave 1 status artifacts are complete and reviewed.

## Acceptance Criteria

- Every Wave 1 task has:
  - contract reference
  - explicit scope
  - command evidence
  - status marker
  - artifacts linked
- No direct push to `main`, no auto-merge, no unscoped protected edits.

## Wave 1 Execution Status

| Task | Contract | Status | Notes |
|---|---|---|---|
| W1-T1 CI/CD truth matrix | `.ai-factory/contracts/w1-ci-truth-matrix.contract.json` | done | Docs-only scope respected |
| W1-T2 docs vs code ground truth | `.ai-factory/contracts/verify-docs-vs-code.contract.json` (narrowed by hard rule) | partial | Mismatches logged; no auto-refactor |
| W1-T3 auth/RBAC audit | `.ai-factory/contracts/audit-rbac.contract.json` | pending human review | Mixed command outcomes; protected-domain review required |
| W1-T4 security housekeeping | `.ai-factory/contracts/w1-security-housekeeping.contract.json` | done | Analysis + remediation plan completed; no upgrades applied |

Wave 1 per-task status artifacts:

- `docs/status/wave1/W1-T1_STATUS.md`
- `docs/status/wave1/W1-T2_STATUS.md`
- `docs/status/wave1/W1-T3_STATUS.md`
- `docs/status/wave1/W1-T4_STATUS.md`
