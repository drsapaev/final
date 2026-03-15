# Next Execution Unit After API Reference Analytics Verification

Follow-up status:

- completed via
  `docs/architecture/W2D_API_REFERENCE_DEPARTMENTS_SERVICES_VERIFICATION.md`

Recommended next step:

- continue `docs/API_REFERENCE.md` verification with another bounded section
  pass rather than a full rewrite

Good next candidates:

- `Doctors`
- `Appointments`

Required entry conditions:

- verify the section against `backend/openapi.json` and the mounted owners
  before editing
- prefer docs-only correction and stale-claim downgrades over runtime changes
- if route families are broader than the current docs framing, document them as
  curated groups instead of inventing a narrow exact inventory

Why:

- `API_REFERENCE.md` is still a curated subset, not a generated specification
- the analytics slice is now complete
- `Departments` and `Services` are also now complete
- `Doctors` and `Appointments` are the next adjacent sections where the same
  kind of old simplified narrative may still exist
