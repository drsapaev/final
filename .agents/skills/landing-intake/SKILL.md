---
name: landing-intake
description: Normalize a raw landing-page request into a structured brief, brand constraints, and measurable success metrics. Use when starting a new landing, rebuilding positioning, or when the prompt is still vague and later agents need explicit assumptions.
---

# Landing Intake

Turn an idea into durable inputs for the rest of the landing pipeline. This skill should write facts and assumptions into the current run folder instead of leaving them in chat only.

## Use This Skill When

- the user says "build me a landing" without a complete brief
- product, audience, or CTA is only partially specified
- later skills need a canonical source of truth for messaging and targets

## Workflow

1. Locate or create the active run folder under `.ai-factory/landing/runs/<run-id>/`.
2. Read or initialize:
   - `briefs/landing_brief.json`
   - `briefs/brand_constraints.json`
   - `briefs/success_metrics.json`
3. Extract the minimum viable brief:
   - product or offer
   - audience
   - primary CTA
   - proof points
   - brand tone
   - constraints and exclusions
4. Convert ambiguity into explicit assumptions. Mark each assumption with a confidence note.
5. Record measurable targets, not only creative goals.

## Output Contract

`landing_brief.json` should contain:

- problem
- promise
- audience
- CTA
- sections
- proof assets
- assumptions

`brand_constraints.json` should contain:

- brand voice
- visual direction
- forbidden patterns
- compliance notes

`success_metrics.json` should contain:

- quality thresholds
- business metrics
- release blockers

## Guardrails

- do not invent customer proof or brand claims
- keep missing inputs visible as assumptions
- if legal or compliance constraints are unclear, mark release as blocked for production
