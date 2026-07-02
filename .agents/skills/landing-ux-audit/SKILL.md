---
name: landing-ux-audit
description: Audit a landing page for user-flow clarity, CTA comprehension, friction, and cognitive load. Use after implementation or when conversion flow feels weak.
---

# Landing UX Audit

Inspect the page from the visitor's perspective and save findings to `audits/ux-audit.json`.

## Review Areas

- first-screen clarity
- CTA wording
- section order and scroll burden
- form friction
- cognitive overload
- ambiguity around what happens next

## Output Contract

- classify issues as critical, medium, or minor
- explain why the issue harms comprehension or progression
- include a concrete fix suggestion for each blocking issue

## Guardrails

- prefer user-path failures over stylistic opinions
- if the CTA is clear and low-friction, do not overcomplicate the page
