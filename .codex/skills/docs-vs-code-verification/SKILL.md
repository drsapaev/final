---
name: docs-vs-code-verification
description: Verify documentation claims against code, tests, and generated contracts in drsapaev/final. Use when docs may overstate status or drift from the implementation.
argument-hint: "[doc path or domain]"
---

# docs-vs-code-verification

## Goal

- Identify and correct drift between documentation and the actual codebase.

## Inputs

- A doc file, topic area, or domain such as `auth`, `queue`, or `payments`.

## Constraints

- Default to docs fixes and findings.
- Do not change protected-domain behavior without a separate approved contract.
- If evidence is incomplete, mark the claim as unverified instead of guessing.

## Workflow

1. Read the target docs.
2. Inspect matching code paths, tests, and generated artifacts such as `backend/openapi.json`.
3. Compare claimed behavior, status, and commands against code and runnable checks.
4. Downgrade stale or optimistic language when verification is missing.

## Verification

- Run the closest code-backed verification command for the changed docs.
- Record mismatches explicitly.

## Expected Artifacts

- Updated docs, mismatch notes, and the command list used for verification.
