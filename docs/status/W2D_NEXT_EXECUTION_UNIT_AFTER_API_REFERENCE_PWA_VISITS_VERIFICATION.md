# Next Execution Unit After API Reference PWA Visits Verification

Follow-up status:

- completed via
  `docs/architecture/W2D_API_REFERENCE_PATIENTS_SCHEDULE_VERIFICATION.md`

Recommended next step:

- continue `docs/API_REFERENCE.md` verification with another bounded section
  pass rather than a full rewrite

Good next candidates:

- `Health`
- `Authentication Header`

Required entry conditions:

- verify the section against `backend/openapi.json` and the mounted owners
  before editing
- prefer docs-only correction and stale-claim downgrades over runtime changes
- if route families or payload shapes are broader than the current docs
  framing, document them as curated groups instead of inventing a narrow exact
  inventory

Why:

- `API_REFERENCE.md` is still a curated subset, not a generated specification
- the `Patient Appointments (PWA)` and `Visits` slice is now complete
- the `Patients` and `Schedule` slice is now also complete
- the remaining low-risk drift is moving toward footer/reference hygiene
  rather than core business-route rewrites
