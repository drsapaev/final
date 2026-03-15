---
name: queue-consistency-audit
description: Audit queue behavior, docs, and tests in drsapaev/final without turning the task into a queue-system rewrite. Use when checking queue parity, routing, or documentation drift.
argument-hint: "[queue flow]"
---

# queue-consistency-audit

## Goal

- Find inconsistencies in queue models, endpoints, UI behavior, and docs.

## Inputs

- Queue feature path, route, endpoint, or report to verify.

## Constraints

- Queue is a protected zone.
- Human review is mandatory for queue behavior changes.
- Do not rewrite numbering, timing, or assignment algorithms under this skill.

## Workflow

1. Inspect the queue code path from backend to frontend.
2. Compare it with queue docs and existing queue tests.
3. Record inconsistencies and only apply bounded, approved corrections.
4. Stop if the task drifts into system redesign.

## Verification

- Run targeted backend queue tests and the nearest frontend queue tests.

## Expected Artifacts

- Queue findings, any approved small fix, and targeted test outcomes.
