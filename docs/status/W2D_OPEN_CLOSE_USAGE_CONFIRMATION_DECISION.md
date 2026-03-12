## Verdict

`POSSIBLE_MANUAL_USAGE_EXISTS`

## Why

### What was not confirmed

- no direct frontend caller of `POST /api/v1/appointments/open-day`
- no direct frontend caller of `POST /api/v1/appointments/close`
- no confirmed backend internal runtime caller beyond the route owners and service mirror

### What was confirmed

- both legacy routes remain mounted and admin-scoped
- the repo still documents the underlying operational workflow as real
- the current frontend uses a newer route, `POST /api/v1/registrar/open-reception`, for the same broad operational concept
- multiple manuals and code comments still describe "Открыть приём" as a registrar action with real consequences

## Decision Meaning

This pass does **not** support treating `open_day` / `close_day` as safely dormant.

It also does **not** support claiming active in-repo usage of the exact legacy routes.

The safest evidence-based position is:

- exact route usage is unconfirmed
- manual or external usage still appears plausible
- behavior changes remain risky until ops-side confirmation is obtained
