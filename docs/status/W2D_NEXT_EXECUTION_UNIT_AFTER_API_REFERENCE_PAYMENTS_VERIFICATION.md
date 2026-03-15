# Next Execution Unit After API Reference Payments Verification

Follow-up status:

- completed via `docs/architecture/W2D_API_REFERENCE_ANALYTICS_VERIFICATION.md`

Recommended next step:

- continue `docs/API_REFERENCE.md` verification with another bounded section
  pass rather than a full rewrite

Good next candidates:

- `Departments`
- `Services`

Required entry conditions:

- verify the section against `backend/openapi.json` and the mounted owners
  before editing
- prefer docs-only correction and stale-claim downgrades over runtime changes
- if route families are broader than the current docs framing, document them as
  curated groups instead of inventing a narrow exact inventory

Why:

- `API_REFERENCE.md` is still a curated subset, not a generated specification
- the analytics slice is now complete
- `Departments` and `Services` are the next adjacent sections where stale
  simplified route summaries are likely to remain
