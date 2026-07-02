---
name: landing-release
description: Assemble the final landing-page QA scorecard, preview summary, and release checklist from prior audit artifacts. Use when preparing a preview or explicit release candidate.
---

# Landing Release

Collect audit evidence and produce the release candidate package. Prefer machine-readable scorecards plus a short human summary.

## Workflow

1. Read all audit artifacts under `audits/`.
2. Update `release/qa-scorecard.json` or run the helper aggregator.
3. Write:
   - `release/preview-summary.md`
   - `release/release-notes.md`
4. Decide one of:
   - ready for preview
   - blocked for fixes
   - ready for production approval

## Guardrails

- do not mark release-ready without evidence files
- production release always requires explicit approval
- unresolved critical issues must remain visible in the summary
