# Next Execution Unit After API Reference Patients Schedule Verification

Follow-up status:

- completed via
  `docs/architecture/W2D_API_REFERENCE_HEALTH_AUTH_HEADER_VERIFICATION.md`

Recommended next step:

- continue `docs/API_REFERENCE.md` verification with another bounded section
  pass rather than a full rewrite

Good next candidates:

- `HTTP Status Codes`
- `Roles & Permissions`

Required entry conditions:

- verify the section against `backend/openapi.json` and the mounted owners
  before editing
- prefer docs-only correction and stale-claim downgrades over runtime changes
- if a section is intentionally generic or generated behavior is minimal,
  document it conservatively instead of padding it into a pseudo-spec

Why:

- `API_REFERENCE.md` is still a curated subset, not a generated specification
- the `Patients` and `Schedule` slice is now complete
- the `Health` and `Authentication Header` slice is now also complete
- the remaining low-risk drift is moving toward generic footer/reference
  hygiene rather than core business-route rewrites
