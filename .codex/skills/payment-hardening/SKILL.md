---
name: payment-hardening
description: Audit or harden payment handling in drsapaev/final with strict boundaries. Use when reviewing provider handling, webhook paths, or payment-side security posture.
argument-hint: "[payment area]"
---

# payment-hardening

## Goal

- Reduce payment risk without expanding into a provider integration rewrite.

## Inputs

- Payment endpoint, provider module, webhook path, or payment test path.

## Constraints

- Payments are a protected zone.
- Human review is mandatory.
- No secret rotation, credential edits, or production webhook reconfiguration under this skill.

## Workflow

1. Inspect the relevant payment code, docs, and tests.
2. Look for validation gaps, unsafe assumptions, and weak operational boundaries.
3. Keep any code change minimal and reviewable.
4. Record anything that remains unverified.

## Verification

- Run the nearest payment unit, integration, or browser-flow tests.

## Expected Artifacts

- Hardening summary, residual risk notes, and test results.
