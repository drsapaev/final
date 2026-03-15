# Next Execution Unit After API Reference Status Codes Roles Verification

Recommended next step:

- completed via
  `docs/architecture/W2D_API_REFERENCE_NEW_MODULES_LINKS_VERIFICATION.md`

Historical next candidates that were taken:

- `New Modules`
- `Links`

Current next step now lives in:

- `docs/status/W2D_NEXT_EXECUTION_UNIT_AFTER_API_REFERENCE_NEW_MODULES_LINKS_VERIFICATION.md`

Required entry conditions:

- verify the section against `backend/openapi.json` and the closest mounted
  owners before editing
- prefer docs-only correction and stale-claim downgrades over runtime changes
- if a footer/reference section is mostly navigational, keep the pass small and
  avoid turning it into a broad product-status rewrite

Why:

- `API_REFERENCE.md` is still a curated subset, not a generated specification
- the `HTTP Status Codes` and `Roles & Permissions` slice is now complete
- the remaining low-risk drift is concentrated in the last reference/footer
  sections
