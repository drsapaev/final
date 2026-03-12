---
name: critical-flow-test-mapping
description: Map critical user and system flows to current test coverage in drsapaev/final. Use when identifying which flows are protected, tested, weakly tested, or untested.
argument-hint: "[flow area]"
---

# critical-flow-test-mapping

## Goal

- Produce a grounded map between critical flows and the tests that cover them.

## Inputs

- A domain such as `auth`, `queue`, `payments`, `emr`, or a release-critical user journey.

## Constraints

- Mapping first, code changes second.
- Do not widen into broad test rewrites unless separately approved.
- Treat missing evidence as a gap, not as implicit coverage.

## Workflow

1. Enumerate the critical flow steps from code and docs.
2. Locate backend, frontend, parity, and browser tests that cover each step.
3. Mark missing, weak, or flaky coverage.
4. Recommend the smallest next tests to add.

## Verification

- Confirm every mapped test file exists and matches the claimed flow.

## Expected Artifacts

- Flow-to-test matrix, identified gaps, and next recommended tests.
