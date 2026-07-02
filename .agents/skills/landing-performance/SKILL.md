---
name: landing-performance
description: Audit a landing page for Lighthouse score, Core Web Vitals, asset weight, and frontend delivery performance. Use before release and after major visual or dependency changes.
---

# Landing Performance

Review runtime performance and save findings to `audits/performance-audit.json`. Update `release/qa-scorecard.json` with measured values when available.

## Review Areas

- Lighthouse scores
- LCP, CLS, and INP
- image and font strategy
- JS bundle size and unused code
- render-blocking resources
- animation cost

## Guardrails

- do not mark pass without measured evidence
- prioritize first-screen speed over decorative complexity
- if a fix hurts accessibility or CTA clarity, note the tradeoff explicitly
