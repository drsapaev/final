# Next Execution Unit After API Reference Health Auth Header Verification

Follow-up status:

- completed via
  `docs/architecture/W2D_API_REFERENCE_STATUS_CODES_ROLES_VERIFICATION.md`

Recommended next step:

- continue `docs/API_REFERENCE.md` verification with another bounded section
  pass rather than a full rewrite

Good next candidates:

- `New Modules`
- `Links`

Required entry conditions:

- verify the section against `backend/openapi.json` and the closest mounted
  owners before editing
- prefer docs-only correction and stale-claim downgrades over runtime changes
- if a footer section is intentionally generic, document it conservatively
  instead of turning it into a pseudo-spec

Why:

- `API_REFERENCE.md` is still a curated subset, not a generated specification
- the `Health` and `Authentication Header` slice is now complete
- the `HTTP Status Codes` and `Roles & Permissions` slice is now also complete
- the remaining low-risk footer drift is concentrated in the last
  reference/navigation sections rather than route-family descriptions
