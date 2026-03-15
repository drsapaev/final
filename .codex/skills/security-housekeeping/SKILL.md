---
name: security-housekeeping
description: Perform low-risk security cleanup and verification in drsapaev/final without entering secret rotation or protected-domain rewrites. Use for bounded hygiene work and follow-up cleanup.
argument-hint: "[security area]"
---

# security-housekeeping

## Goal

- Clean up small security debt items that are safe to handle inside setup or bounded maintenance scope.

## Inputs

- Security note, finding, doc claim, or low-risk code path to verify.

## Constraints

- No secret rotation.
- No auth, payment, queue, or EMR rewrites.
- Prefer docs, validation, tests, or config hygiene over deep behavior changes.

## Workflow

1. Confirm the security concern from code, config, or docs.
2. Apply a minimal cleanup if it stays outside protected behavior.
3. Record any higher-risk item as pending instead of forcing it into this task.

## Verification

- Run the narrowest relevant test or static check for the cleaned-up area.

## Expected Artifacts

- Security housekeeping summary, verification notes, and deferred higher-risk items.
