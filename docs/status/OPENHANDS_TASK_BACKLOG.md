# OpenHands Task Backlog

Date: 2026-03-06

## Status Legend

- `done`
- `partial`
- `blocked`
- `pending human review`
- `pending`

## Backlog

| ID | Title | Wave | Contract | Risk | Status | Notes |
|---|---|---|---|---|---|---|
| W1-T1 | CI/CD truth matrix and status bootstrap | stabilization | `w1-ci-truth-matrix.contract.json` | low | done | Docs-only rule enforced |
| W1-T2 | Docs vs code ground truth | stabilization | `verify-docs-vs-code.contract.json` | medium | partial | Mismatch inventory completed; no auto-refactor |
| W1-T3 | Auth/RBAC audit | stabilization | `audit-rbac.contract.json` | high | pending human review | Protected-domain audit with mixed command outcomes |
| W1-T4 | Security housekeeping baseline | stabilization | `w1-security-housekeeping.contract.json` | high | done | Analysis-only; dependency upgrades intentionally skipped |
| W15-T1 | Frontend CI blocker fix (`TwoFactorManager` mock/export) | stabilization | `stabilize-ci.contract.json` | medium | done | Full `frontend` test run is green after test-only fix |
| W15-T2 | Stabilize `test_role_routing.py` | stabilization | `audit-rbac.contract.json` (narrowed) | medium | done | Replaced flaky live check with deterministic RBAC matrix wrapper |
| W15-T3 | Docs normalization (risk claims) | stabilization | `cleanup-docs.contract.json` (narrowed) | low | partial | High-visibility claims normalized; broad legacy sweep deferred |
| W15-T4 | Security remediation slice A (frontend deps) | stabilization | `harden-payments.contract.json` (frontend-only narrowed) | high | partial | Reduced audit findings with non-major updates; 1 critical + 3 high remain |
| W15-T5 | Security remediation slice B (bandit safe fixes) | stabilization | `security-housekeeping` narrowed | high | pending human review | Safe non-protected B324 fixed; remaining high include protected payment paths |
| W175-T1 | CI stability recheck | gate-readiness | `stabilize-ci.contract.json` (recheck mode) | high | partial | Frontend/RBAC green; backend root `pytest -q` unstable due `test_cart_direct.py` side effects |
| W175-T2 | Security risk re-evaluation | gate-readiness | `security-housekeeping` recheck | high | done | Security baseline revalidated; no regression from W1.5 |
| W175-T3 | Protected-zone findings classification | gate-readiness | audit classification | high | done | Payment/template/pdf/encryption findings mapped to classes 1-4 |
| W175-T4 | jsPDF critical dependency decision | gate-readiness | dependency decision note | high | done | Chosen path: temporary mitigation; major upgrade remains pending |
| W175-T5 | Wave 2 gate decision | gate-readiness | gate verdict | high | done | `NOT_READY_FOR_WAVE2` with explicit blockers |
| W2-T1 | Frontend CI blocker fix (`TwoFactorManager` mock) | stabilization | `stabilize-ci.contract.json` | medium | done | Closed by `W15-T1` |
| W2-T2 | PR backlog consolidation (Palette/Dependabot) | stabilization | `polish-core.contract.json` (narrowed) | medium | pending | Needs human decision on close/supersede |
| W2-T3 | Frontend/backend contract audit refresh | structural hardening | `audit-contracts.contract.json` | high | pending | Rebuild parity from latest OpenAPI + inventory |
| W2-T4 | Queue consistency audit | structural hardening | `audit-queue.contract.json` | high | pending human review | Protected queue domain |
| W2-T5 | Payment hardening audit | structural hardening | `harden-payments.contract.json` | high | pending human review | Protected payment domain |
| W2-T6 | Service/repository refactor slice (non-protected) | structural hardening | `refactor-module.contract.json` | medium | pending | Must stay outside protected services |
| W3-T1 | Accessibility batch merge | polish | `polish-accessibility.contract.json` | medium | pending | Non-protected UI surfaces only |
| W3-T2 | Docs/root cleanup | polish | `cleanup-docs.contract.json` | low | pending | Remove stale optimistic claims |

## Wave 1 Notes

- Hard rule W1-T1: no code modifications.
- Hard rule W1-T2: mismatch reported, no auto-refactor.
- Hard rule W1-T4: analysis/remediation plan only, no dependency upgrades.
- Per-task status artifacts:
  - `docs/status/wave1/W1-T1_STATUS.md`
  - `docs/status/wave1/W1-T2_STATUS.md`
  - `docs/status/wave1/W1-T3_STATUS.md`
  - `docs/status/wave1/W1-T4_STATUS.md`

## Wave 1.5 Notes

- W1.5 status artifacts:
  - `docs/status/wave15/W15-T1_STATUS.md`
  - `docs/status/wave15/W15-T2_STATUS.md`
  - `docs/status/wave15/W15-T3_STATUS.md`
  - `docs/security/wave15/W15-T4_SECURITY_SLICE_A.md`
  - `docs/security/wave15/W15-T5_SECURITY_SLICE_B.md`

## Wave 1.75 Notes

- W1.75 artifacts:
  - `docs/status/wave175/W175-T1_CI_STABILITY.md`
  - `docs/security/wave175/W175_SECURITY_RECHECK.md`
  - `docs/security/wave175/W175_PROTECTED_ZONE_REVIEW.md`
  - `docs/security/wave175/W175_JSPDF_RISK_DECISION.md`
  - `docs/status/WAVE2_GATE_DECISION.md`
- Gate verdict: `NOT_READY_FOR_WAVE2`.
