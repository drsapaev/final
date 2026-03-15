# Next Execution Unit After API Reference Queue Verification

Follow-up status:

- completed via `docs/architecture/W2D_API_REFERENCE_PAYMENTS_VERIFICATION.md`

Recommended next step:

- continue `docs/API_REFERENCE.md` verification with another bounded section
  pass rather than a full rewrite

Best next candidate:

- `Analytics`

Required entry conditions:

- verify the section against `backend/openapi.json` and the mounted payment
  owners before editing
- prefer docs-only correction and stale-claim downgrades over runtime changes
- if payment response shapes are divergent or under-typed, document that
  conservatively instead of guessing

Why:

- `API_REFERENCE.md` is still a curated subset, not a generated specification
- the queue slice found substantial route drift while staying fully docs-first
- analytics are the next adjacent surface where stale docs can still mislead
  readers
