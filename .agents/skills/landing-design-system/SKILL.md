---
name: landing-design-system
description: Define design tokens, typography, spacing, and component rules for a landing page. Use before or alongside UI implementation to prevent inconsistent AI-generated design.
---

# Landing Design System

This skill prevents random pretty UI by establishing tokens and component constraints first. It should write to `design/tokens.json` and `design/layout-spec.json`.

## Workflow

1. Read the brief and strategy outputs.
2. Define:
   - color roles
   - typography scale
   - spacing scale
   - radius, borders, shadows
   - section container rules
3. Map tokens to component primitives:
   - buttons
   - cards
   - badges
   - inputs
   - nav and footer
4. Record mobile and desktop behavior in `design/layout-spec.json`.

## Guardrails

- preserve an intentional visual direction instead of defaulting to generic UI
- avoid token sprawl; each token needs a real job
- define contrast-safe pairs for all key surfaces
- motion must support hierarchy, not distract from CTA
