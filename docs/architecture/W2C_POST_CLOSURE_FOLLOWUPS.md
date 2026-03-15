# Wave 2C Post-Closure Follow-Ups

Date: 2026-03-09
Mode: analysis-first, docs-only

## Purpose

This document defines the post-closure follow-up buckets after Wave 2C.

These are not blockers for Wave 2C completion. They are next-stage technical
work.

## 1. OnlineDay deprecation / cleanup track

Goal:

- retire or replace the remaining mounted OnlineDay legacy surface

Includes:

- legacy day open/close administration
- legacy board/stats visibility
- legacy `last_ticket` allocator path

## 2. Force majeure correction / contract follow-up

Goal:

- handle local force_majeure drift candidates without forcing the domain into
  the ordinary allocator track

Candidates:

- duplicate gate on the target tomorrow queue
- monotonic numbering with cancelled-history rows
- business clarification for pending-entry eligibility

## 3. Dead / duplicate queue cleanup

Goal:

- remove disabled routers, duplicate service mirrors, and stale helpers once
  ownership is confirmed

Candidates:

- disabled legacy queue routers
- duplicate API service mirrors
- stale queue cleanup helpers

## 4. Postgres-aligned test follow-up

Goal:

- reduce drift between production queue behavior and test infrastructure

Why relevant:

- `backend/.env` uses Postgres
- `backend/tests/conftest.py` still provisions SQLite for pytest
- allocator and concurrency behavior are especially sensitive to DB semantics

This is not a Wave 2C blocker, but it is a meaningful follow-up bucket.

## 5. Docs cleanup / architecture consolidation

Goal:

- consolidate Wave 2C docs into a stable end-state architecture set
- reduce drift between status docs and top-level architecture docs

Examples:

- closure summary
- migration-strategy consolidation
- cleanup of superseded intermediate status docs if desired later

## Follow-up verdict

Wave 2C ends with a clean boundary architecture, but it intentionally leaves:

- legacy retirement
- exceptional-domain refinement
- cleanup
- infrastructure alignment

for post-closure work.
