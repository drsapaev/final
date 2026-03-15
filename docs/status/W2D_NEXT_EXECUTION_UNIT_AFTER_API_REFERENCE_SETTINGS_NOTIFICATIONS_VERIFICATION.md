# Next Execution Unit After API Reference Settings and Notifications Verification

Follow-up status:

- completed via `docs/architecture/W2D_API_REFERENCE_AUTH_USERS_VERIFICATION.md`

Recommended next step:

- continue `docs/API_REFERENCE.md` verification with another bounded section
  pass rather than a full rewrite

Good next candidates:

- `Authentication` and `Users`
- `Queue`
- `Payments`

Required entry conditions:

- verify each section against `backend/openapi.json` before editing
- downgrade stale or optimistic claims instead of guessing
- keep protected runtime code out of scope unless a separate approved contract
  change is actually required

Why:

- `API_REFERENCE.md` is clearly still a curated subset, not a generated spec
- bounded verification keeps the cleanup honest and low-risk
- the notifications/settings slice already proved that high-value drift still
  exists inside this document
