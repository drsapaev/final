# W2D Env Setup Guide Verification

## Summary

This was a bounded docs-vs-code audit for:

- `backend/env_setup_guide.md`

The goal was not to create a full new env architecture. The goal was to stop
an older quick-start note from competing with the current env templates and
production/setup docs.

## Findings

### The guide still taught users to create an empty `.env` manually

- it told readers to create `.env` from scratch
- but the repo now already has a live `backend/.env.example`
- the honest docs move was to make the guide point to the template first,
  instead of duplicating a partial env block inline as the primary workflow

### The guide still carried stale CORS values and older framing

- it still advertised `localhost:4173` in the example block
- the current `backend/.env.example` now uses:
  - `http://localhost:5173`
  - `http://127.0.0.1:5173`
- it also needed to explain that the backend accepts both `CORS_ORIGINS` and
  `BACKEND_CORS_ORIGINS`

### The file had dead FCM guide links

- `backend/env_setup_guide.md` referenced `docs/FCM_SETUP_GUIDE.md`
- that repo-local document does not currently exist
- the honest fix was to remove those dead-link claims instead of preserving a
  nonexistent setup path

## What changed

- rewrote `backend/env_setup_guide.md` into a dev-first env setup guide with
  current caveats
- moved the primary workflow to `copy .env.example -> .env`
- aligned the minimum env guidance with the current template and backend config
- removed the dead `FCM_SETUP_GUIDE.md` references
- added explicit pointers to:
  - `backend/.env.example`
  - `backend/SETUP_PRODUCTION.md`
  - `ops/.env.example`

## Evidence used

- `backend/env_setup_guide.md`
- `backend/.env.example`
- `ops/.env.example`
- `backend/app/core/config.py`

## Verification

- `pytest tests/test_openapi_contract.py -q`

## Recommended next step

Continue the neighboring env/template cleanup with:

- `backend/.env.example`

Why:

- after the guide is normalized, the next honest low-risk follow-up is a
  bounded template audit to make sure the comments and naming in the template
  still match the current backend config and the newer ops docs
