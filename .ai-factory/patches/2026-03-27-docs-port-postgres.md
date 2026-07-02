# Patch: README and runbooks aligned to backend 18000 / Postgres-first

**Date:** 2026-03-27

## Context

The local dev and runbook docs still contained startup instructions that pointed to the old `8000`-style launch flow and referenced SQLite-era guidance.

## Changes

- Updated `README.md` backend start command to use `python run_server.py`
- Updated `docs/runbooks/LOCAL_DEV_ONBOARDING.md` to use `python run_server.py` and keep the Postgres-first scope explicit
- Updated `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md` to remove the SQLite-specific wording from the data-closure note
- Updated `docs/runbooks/POSTGRES_DR_RUNBOOK.md` to describe the legacy `clinic.db` snapshot without presenting SQLite as an active operational instruction

## Verification

- Targeted search across the affected docs no longer finds standalone `8000` or `sqlite` instructions
- `README.md` and onboarding docs now point at the canonical backend launch path used by the current runtime

## Notes

This keeps the docs aligned with the current Postgres-based local runtime and the backend default port `18000`.
