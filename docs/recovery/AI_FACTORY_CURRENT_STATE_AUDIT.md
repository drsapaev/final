# AI Factory Current State Audit

## Executive Summary

Current `origin/main` already implements most of the substantive AI Factory intent around:

- EMR v2 hard cutover and canonical `visit_id` handling
- queue SSOT and realtime queue core
- notifications / messaging contract modernization
- CI guardrails, security scanning, and operational runbooks
- panel QA acceptance docs and evidence trails

The AI Factory artifacts are now split into three clear buckets:

1. **Source of truth** — current operational docs + current code
2. **Historical evidence** — execution logs, rollout evidence, plan history
3. **Stale / deprecated** — older architecture or migration docs that should not be treated as current truth

## What Is Already Implemented in Current Main

- Modular monolith boundaries and service/repository layering.
- Postgres + Alembic as the operational data SSOT.
- Queue SSOT (`DailyQueue`, `OnlineQueueEntry`, `QueueToken`) and realtime queue updates.
- EMR v2 hard-cutover path with canonical `visit_id`.
- Backend-owned notification inbox and WS normalization.
- Versioned chat messaging contract with reliable vs ephemeral events.
- GitHub-native CI guardrails and security scan workflows.
- Current panel QA checklist and acceptance contour.

## What Is Partially Implemented

- Load / capacity engineering: the workflow and runbook exist, but the audit did not prove a complete per-profile enforcement loop for every critical group.
- Observability / SLA: structured logs and metrics are documented, but the audit did not prove a single end-to-end proof chain for every alert/review loop.
- VPS promotion: the rollout path is documented, but current main does not prove the Linux VPS contour has been executed and soaked.
- Multi-clinic / interoperability: the roadmap says this is done, but the audit could not fully re-confirm the runtime story from the current main evidence set.

## What Exists Only in Docs or Logs

- Historical messaging QA and contract docs.
- Historical panel QA progress log.
- Historical queue fix and migration reports.
- AI Factory evolution notes and patch-history bundles.
- Recovery audit artifacts from earlier workflows.

These are useful for audit trail, but they are not the live product SSOT.

## What Is Stale

- Old notification architecture docs that still describe sender-service / Celery-era behavior.
- Old queue implementation / migration docs that predate the current queue SSOT.
- Archived queue / panel improvement plans.
- Any artifact that still implies `OnlineDay` / legacy queue docs are current implementation guidance.

## 5-10 Gaps Still Worth Doing

1. VPS promotion end-to-end proof.
2. VPS soak / rollback automation proof.
3. Stronger load budget enforcement by endpoint profile.
4. Better observability SLA closure proof.
5. Multi-clinic / tenant-isolation verification.

## What To Close and Stop Touching

- Do not continue the old sender-service notification architecture.
- Do not continue legacy queue migration docs as if they were live guidance.
- Do not treat messaging audit or panel QA logs as current truth.
- Do not reopen old EMR or queue histories as product work.

## Source-of-Truth Classification

- **Source of truth:** current `origin/main`, current runbooks, current SSOT docs for queue / EMR / CI / security.
- **Historical evidence:** `.ai-factory/logs/*`, `.ai-factory/evolutions/*`, `.ai-factory/patches/*`, old messaging/queue runbooks.
- **Stale / deprecated:** old notification architecture doc, archived queue docs, superseded queue fix plans, old implementation narratives.

## Verdict

**Current main already supersedes most AI Factory docs.**

The docs are not mostly ahead of code; instead, most of the AI Factory story is now either implemented in current main or preserved as historical evidence. The remaining meaningful work is concentrated in ops / rollout / capacity / interoperability follow-ups, not in broad runtime recovery.

## Safest Next Action

- Keep current main as the product truth.
- Archive or relabel the stale historical docs.
- Open a separate small ops track only if VPS promotion or stronger capacity enforcement is truly next.

