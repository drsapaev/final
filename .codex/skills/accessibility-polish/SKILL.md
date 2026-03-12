---
name: accessibility-polish
description: Apply bounded accessibility improvements to non-protected UI surfaces in drsapaev/final. Use for small semantic, keyboard, contrast, or labeling fixes.
argument-hint: "[component or page]"
---

# accessibility-polish

## Goal

- Improve accessibility in a narrow UI slice without spilling into protected workflows.

## Inputs

- Component path, page path, or accessibility issue description.

## Constraints

- Stay out of auth, payments, queue, and EMR by default.
- Keep the work limited to targeted a11y improvements.
- Do not redesign entire pages under this skill.

## Workflow

1. Inspect the targeted UI and its existing tests.
2. Apply the smallest semantic or interaction fix that addresses the issue.
3. Update or add targeted accessibility checks when appropriate.
4. Stop if the change requires protected-domain flow edits.

## Verification

- Run the nearest accessibility-focused Vitest or Playwright coverage.

## Expected Artifacts

- Accessibility fix summary, changed tests, and any remaining gaps.
