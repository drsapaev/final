# OpenHands First 10 Tasks

Historical status:
- this is an early-phase task snapshot from 2026-03-06 and not the current
  execution queue

Current SSOT:
- `docs/status/W2D_STATUS_NAVIGATION_INDEX.md`
- `docs/status/AI_FACTORY_OPENHANDS_MASTER_PLAN.md`
- `docs/status/OPENHANDS_TASK_BACKLOG.md`

Date: 2026-03-06

## Execution-Ready Set

| # | ID | Title | Contract | Current status |
|---|---|---|---|---|
| 1 | W1-T1 | CI/CD truth matrix and status bootstrap | `w1-ci-truth-matrix.contract.json` | done |
| 2 | W1-T2 | Docs vs code ground truth | `verify-docs-vs-code.contract.json` | partial |
| 3 | W1-T3 | Auth/RBAC audit | `audit-rbac.contract.json` | pending human review |
| 4 | W1-T4 | Security housekeeping baseline | `w1-security-housekeeping.contract.json` | done |
| 5 | W2-T1 | Frontend CI blocker fix (`TwoFactorManager` mock) | `stabilize-ci.contract.json` | pending |
| 6 | W2-T2 | PR backlog consolidation | `polish-core.contract.json` (narrowed) | pending |
| 7 | W2-T3 | Contract audit refresh | `audit-contracts.contract.json` | pending |
| 8 | W2-T4 | Queue consistency audit | `audit-queue.contract.json` | pending human review |
| 9 | W2-T5 | Payment hardening audit | `harden-payments.contract.json` | pending human review |
| 10 | W2-T6 | Service/repository non-protected slice | `refactor-module.contract.json` | pending |

## Hard Rules Applied In Wave 1

1. W1-T1: no code modifications, docs/reports only.
2. W1-T2: report mismatches, do not auto-refactor code.
3. W1-T4: dependency upgrades are out of scope.

Wave 1 per-task statuses:

- `docs/status/wave1/W1-T1_STATUS.md`
- `docs/status/wave1/W1-T2_STATUS.md`
- `docs/status/wave1/W1-T3_STATUS.md`
- `docs/status/wave1/W1-T4_STATUS.md`
