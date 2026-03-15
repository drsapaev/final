# Next Execution Unit After API Reference Departments Services Verification

Follow-up status:

- completed via
  `docs/architecture/W2D_API_REFERENCE_DOCTORS_APPOINTMENTS_VERIFICATION.md`

Recommended next step:

- continue `docs/API_REFERENCE.md` verification with another bounded section
  pass rather than a full rewrite

Good next candidates:

- `Patient Appointments (PWA)`
- `Visits`

Required entry conditions:

- verify the section against `backend/openapi.json` and the mounted owners
  before editing
- prefer docs-only correction and stale-claim downgrades over runtime changes
- if route families or access notes are broader than the current docs framing,
  document them as curated groups instead of inventing a narrow exact
  inventory

Why:

- `API_REFERENCE.md` is still a curated subset, not a generated specification
- the `Departments` and `Services` slice is now complete
- the `Doctors` and `Appointments` slice is now also complete
- the patient-facing appointment and visit sections are the next nearby places
  where older optimistic workflow summaries may still drift from code
