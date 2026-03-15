# AI Automation Guardrails

Date: 2026-03-06

## Purpose

These guardrails define what AI Factory and OpenHands may do in this repo during bounded automation work.

## Default Operating Mode

- PR-only mode
- no direct push to `main`
- no auto-merge
- no production secret changes
- no "improve everything" or repo-wide sweep behavior

## What Agents May Do

Allowed without extra approval when the task is small and outside protected zones:

- inspect code and docs
- update status docs, runbooks, and contracts
- add or adjust bounded tests
- perform narrow UI polish outside auth/payment/queue/EMR
- stabilize a single CI job with targeted changes
- render or validate execution contracts

## What Agents May Not Do

- push directly to `main`
- rotate or replace production secrets
- change workflow permissions without explicit human approval
- alter auth, payments, queue, EMR, or migrations autonomously
- run broad refactors across backend and frontend
- remove safeguards to make tests pass
- auto-merge or self-approve

## Human Review Is Mandatory When

- any protected zone is touched
- a contract exceeds default file or diff budgets
- auth/RBAC behavior changes
- payment behavior or provider handling changes
- queue numbering, queue state, or queue timing logic changes
- EMR persistence, versioning, or audit behavior changes
- Alembic or schema files change
- workflow permissions or branch protection assumptions change

## Protected Zones

Protected by default:

- `backend/app/api/v1/endpoints/auth*.py`
- `backend/app/core/auth.py`
- `backend/app/core/security.py`
- `backend/app/core/rbac.py`
- `backend/app/services/payment*`
- `backend/app/repositories/payment*`
- `backend/app/models/payment*`
- `backend/app/api/v1/endpoints/payment*`
- `backend/app/services/queue*`
- `backend/app/repositories/queue*`
- `backend/app/models/online_queue.py`
- `backend/app/api/v1/endpoints/queue*.py`
- `backend/app/services/emr*`
- `backend/app/models/emr*`
- `backend/app/api/v1/endpoints/emr*.py`
- `backend/alembic/**`
- `backend/.env`
- `backend/.secret_key`
- `.secret_key`
- `.github/workflows/**`

## Default Budgets

- `max_files_changed = 10`
- `max_diff_lines = 400`

If a task cannot stay within these limits, it must stop and request human review or a revised contract.

## Forbidden Auto-Execution Task Classes

- schema or Alembic migration authoring
- auth token flow rewrites
- payment provider secret or webhook signature changes
- queue algorithm rewrites
- EMR audit-trail or clinical record behavior changes
- permission-model rewrites
- dependency sweep upgrades across the repo
- repo-wide lint or formatting rewrites
- workflow permission escalation
- production deploy, rollback, or environment mutation

## Required Output From Every Automated Task

- a short change summary
- exact files changed
- tests run and results
- explicit note of anything partial, blocked, or deferred

## Escalation Rule

If a task starts as "small polish" but drifts toward protected behavior, stop. Do not silently continue under the old contract.
