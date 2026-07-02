---
name: landing-seo
description: Audit a landing page for metadata, heading structure, schema coverage, and crawlability. Use before preview or release to keep search-facing quality measurable.
---

# Landing SEO

Review the landing like a technical SEO specialist and write the result to `audits/seo-audit.json`.

## Review Areas

- title and meta description quality
- canonical and indexability signals
- heading structure
- semantic HTML
- structured data coverage
- internal linking and crawl hints
- asset and content choices that hurt discoverability

## Required Outputs

- critical, medium, and minor issues
- concrete fixes with file or section targets
- measured or observed evidence when available
- `status` set to `passed`, `failed`, or `pending`

## Guardrails

- do not confuse copywriting style with SEO defects unless discoverability is affected
- schema suggestions must match content that actually exists on the page
