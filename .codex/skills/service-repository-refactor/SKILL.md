---
name: service-repository-refactor
description: Perform a bounded service or repository refactor in drsapaev/final without crossing protected modules. Use for small structural cleanup in a single backend module.
argument-hint: "[module path]"
---

# service-repository-refactor

## Goal

- Improve one backend module's service and repository structure while preserving behavior.

## Inputs

- The target module or path and the specific structural problem.

## Constraints

- One module at a time.
- No auth, payments, queue, EMR, alembic, or workflow-permission changes unless explicitly approved elsewhere.
- Preserve existing contracts and behavior.

## Workflow

1. Map endpoint, service, repository, and test usage for the target module.
2. Move logic toward the intended service or repository boundary.
3. Keep diffs small and behavior-preserving.
4. Update targeted tests only as needed.

## Verification

- Run the nearest backend tests plus architecture boundary checks if imports moved.

## Expected Artifacts

- Refactor summary, changed files, and targeted test results.
