---
name: landing-accessibility
description: Audit a landing page for WCAG alignment, keyboard access, semantic structure, and assistive-technology usability. Use before release and after major UI changes.
---

# Landing Accessibility

Check the page with both semantic review and test evidence. Save the result to `audits/accessibility-audit.json`.

## Review Areas

- heading order and landmark usage
- button and link naming
- label and input associations
- keyboard navigation and focus visibility
- color contrast
- motion and reduced-motion support
- image alt text and decorative media handling

## Required Evidence

- mention whether Axe or equivalent automated checks were run
- call out any manual keyboard or screen-reader risks not covered by automation

## Guardrails

- a page cannot pass while critical Axe issues remain
- missing semantics or broken focus order are always blocking
