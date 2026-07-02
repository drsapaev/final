# AI Factory Doc Inventory

> This inventory is scoped to AI Factory intent, execution history, and the operational docs that those artifacts reference.

## Core AI Factory Sources

| Path | Type | Theme / domain | Approximate intent | Audit role |
|---|---|---|---|---|
| `.ai-factory/DESCRIPTION.md` | description | project overview / runtime defaults | Defines the product, stack, and current contour | Source of intent |
| `.ai-factory/ARCHITECTURE.md` | architecture | modular monolith / domain modules | Defines the layered architecture and dependency rules | Source of intent |
| `.ai-factory/RULES.md` | rules | execution constraints | Defines repo rules, especially EMR and UI boundaries | Source of intent |
| `.ai-factory/ROADMAP.md` | roadmap | milestones / status | Tracks completed milestones and the remaining VPS milestone | Source of intent + status |
| `.ai-factory/PLAN.md` | plan / backlog | panel QA, EMR, security, SLO | Long-running implementation plan with execution evidence | Source of execution history |

## AI Factory Plans, Logs, and Evolutions

| Path | Type | Theme / domain | Approximate intent | Audit role |
|---|---|---|---|---|
| `.ai-factory/plans/feat-unified-notifications-strong.md` | plan | notifications | Backend-owned notification platform, inbox, WS compatibility, guardrails | Source of intent |
| `.ai-factory/plans/messaging-stack-modernization.md` | plan | messaging / chat | Contract-first messaging modernization and rollout history | Historical artifact / evidence |
| `.ai-factory/logs/MESSAGING_AUDIT_STATUS.md` | log | messaging | Tracks audit findings, blockers, and rollout evidence | Execution evidence only |
| `.ai-factory/logs/PANEL_QA_IMPLEMENTATION_STATUS.md` | log | panel QA / acceptance | Tracks role-by-role smoke progress and proof | Execution evidence only |
| `.ai-factory/evolutions/2026-03-28-00.11.md` | evolution | AI Factory skill-context / runtime defaults | Records context updates and drift patterns | Historical evidence |
| `.ai-factory/patches/*.md` | patch notes bundle | many domains | Patch-level historical evidence across queue, EMR, CI, UI, and settings | Historical evidence bundle |

## Current Operational Docs That Matter

| Path | Type | Theme / domain | Approximate intent | Audit role |
|---|---|---|---|---|
| `docs/CI_GUARDRAILS.md` | guide | CI / merge policy | Explains required merge gates and architecture guardrails | Current operator truth |
| `docs/NOTIFICATION_SYSTEM_ARCHITECTURE.md` | architecture guide | notifications | Describes the old sender-service architecture | Historical / deprecated |
| `docs/QUEUE_SYSTEM_ARCHITECTURE.md` | architecture guide | queue | SSOT guide for the current queue model | Current operator truth |
| `docs/ONLINE_QUEUE_SYSTEM_V2.md` | product doc | queue | Explains queue behavior and lifecycle to operators | Current operational reference |
| `docs/PANEL_QA_CHECKLIST.md` | runbook | panel QA / acceptance | Primary acceptance checklist and execution discipline | Current operator truth |
| `docs/runbooks/MESSAGING_CONTRACT.md` | runbook | messaging | Historical messaging contract and delivery semantics | Historical evidence |
| `docs/runbooks/MESSAGING_QA_CHECKLIST.md` | runbook | messaging QA | Historical messaging smoke checklist | Historical evidence |
| `docs/runbooks/EMR_V2_HARD_CUTOVER_RUNBOOK.md` | runbook | EMR | Canonical cutover and backfill procedure | Current operator truth |
| `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md` | runbook | local staging / acceptance | Primary local acceptance contour and exit criteria | Current operator truth |
| `docs/runbooks/LOAD_TESTING_RUNBOOK.md` | runbook | load / SLO | Load profiles, thresholds, and regression policy | Current operational reference |
| `docs/runbooks/OBSERVABILITY_SLA_RUNBOOK.md` | runbook | observability / SLA | Metrics, thresholds, and alert policy | Current operational reference |
| `docs/runbooks/VPS_HOST_ROLLOUT_RUNBOOK.md` | runbook | deployment / VPS | Production promotion path from local staging to VPS | Future-track operational reference |
| `docs/PRODUCTION_SECURITY.md` | guide | security / ops | Production security posture, env vars, rate limiting, logging | Current operational reference |

## Historical / Deprecated Docs

| Path | Type | Theme / domain | Approximate intent | Audit role |
|---|---|---|---|---|
| `docs/archives/*` | archive bundle | queue / panel / general refactors | Superseded queue, panel, and migration notes | Historical / deprecated |

## Notes

- The audit treats `.ai-factory/skill-context/*` as tool-context, not product intent.
- `docs/recovery/*` files are audit artifacts produced by this analysis and are not product source of truth.

