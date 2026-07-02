---
name: landing-design-audit
description: Audit a landing page for visual hierarchy, spacing, contrast, and component consistency. Use after implementation or after major visual changes.
---

# Landing Design Audit

Inspect the implemented landing like a senior visual designer. The result should be saved to `audits/design-audit.json`.

## Review Areas

- visual hierarchy on the first screen
- spacing rhythm
- typography contrast and scale
- CTA prominence
- consistency of cards, buttons, badges, and iconography
- visual noise and over-decoration

## Output Contract

Return only:

- `critical_issues`
- `medium_issues`
- `minor_improvements`
- `recommendations`
- `status`

Each issue should point to a section, component, or file.

## Guardrails

- do not judge aesthetics in isolation from conversion intent
- mark a critical issue only when it materially hurts comprehension or trust
