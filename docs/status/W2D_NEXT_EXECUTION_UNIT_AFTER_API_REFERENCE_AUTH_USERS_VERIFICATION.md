# Next Execution Unit After API Reference Authentication and Users Verification

Follow-up status:

- completed via `docs/architecture/W2D_API_REFERENCE_QUEUE_VERIFICATION.md`

Recommended next step:

- continue `docs/API_REFERENCE.md` verification with another bounded section
  pass rather than a full rewrite

Good next candidates:

- `Payments`

Required entry conditions:

- verify each section against `backend/openapi.json` and the mounted endpoint
  owners before editing
- prefer downgrading stale or optimistic claims over guessing exact behavior
- keep protected runtime code out of scope unless a separate approved contract
  change is actually required

Why:

- `API_REFERENCE.md` is still a curated subset, not a generated specification
- the auth/users slice found real route and access drift without needing a
  runtime rewrite
- `Payments` remain the next high-value section where docs accuracy matters,
  but the pass should stay docs-first
