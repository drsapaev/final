---
name: landing-visual-qa
description: Inspect screenshots or live renders for layout regressions, alignment problems, and responsive breakpoints. Use after implementation and after visual fixes.
---

# Landing Visual QA

Use screenshots or browser inspection to catch layout bugs that code review misses. Save findings to `audits/visual-audit.json`.

## Review Areas

- alignment and spacing drift
- overflow, wrapping, and clipping
- desktop to mobile breakpoint quality
- unexpected empty areas
- mis-sized media
- sticky header or CTA overlap

## Guardrails

- always inspect both desktop and mobile states
- screenshots complement code review; they do not replace semantic checks
