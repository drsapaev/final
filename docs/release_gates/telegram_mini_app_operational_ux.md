# Telegram Bot + Mini App Operational UX Release Gate

## Purpose

This document is the canonical release gate for the Telegram Bot + Mini App patient onboarding workflow.

Current evidence status for the scoped onboarding release:

- final score: `100/100`
- privacy gate: `Pass`
- P0: `0`
- P1: `0`
- detailed evidence: `docs/release_gates/telegram_mini_app_score_100_evidence.md`

The product path under review is:

`patient -> registrar -> queue -> doctor / EMR -> payment -> reports`

The onboarding guardrail remains strict:

`Unknown patients can request booking, but cannot become Patients or confirmed Visits until Registrar/Admin review.`

## Hard Rules

1. No score can compensate for a failed privacy gate.
2. Every screen must have a next safe action.
3. Unknown users may submit onboarding requests only.
4. Unknown users must not auto-create Patient rows.
5. Unknown users must not auto-create confirmed Appointments or Visits.
6. Onboarding scope must not access queue, payments, documents, results, or EMR-linked data.
7. Telegram, Mini App, logs, telemetry, CSV export, and release evidence must never expose raw entry tokens, raw payment ids, diagnosis, lab details, EMR content, or raw backend payloads.

## Evidence Categories

- Telegram informativity
- Mini App informativity
- Telegram usability
- Mini App usability
- Patient utility
- Staff utility
- Business utility

## Mandatory Evidence

- Backend onboarding/privacy tests
- OpenAPI contract tests
- Frontend Telegram + Mini App tests
- Frontend production build
- Alembic heads/history
- Disposable DB upgrade when `DATABASE_URL_TEST` is available
- Browser QA artifacts for `375`, `768`, `1280`, `1920`
- Privacy grep pass across checked UI/evidence files
- Onboarding analytics event whitelist
- Release evidence report and score JSON

## Current Safe Scope

The current implementation scope for this gate is intentionally narrow:

- Telegram onboarding policy
- Registrar duplicate-safe review workflow
- TelegramManager operational inbox
- Mini App onboarding shell and protected-state guardrails
- Safe onboarding analytics and masked export
- Release gate automation and evidence docs
