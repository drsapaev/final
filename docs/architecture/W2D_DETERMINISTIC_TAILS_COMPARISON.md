# Wave 2D Deterministic Tails Comparison

Date: 2026-03-10

## Comparison Matrix

| Track | Architectural leverage | Regression risk | Human/business dependency | Cleanup/deprecation value | Long-term maintainability impact | Speed of safe progress |
| --- | --- | --- | --- | --- | --- | --- |
| OnlineDay deprecation continuation | High | High | High / partial | High | High | Low |
| Test infrastructure / Postgres-aligned follow-up | High | Medium | Low | Medium | High | Medium |
| Docs / architecture consolidation | Medium | Low | Low | Medium | Medium to High | High |
| Support/test-only residue cleanup | Medium-low | Low to Medium | Low | Medium | Medium | Medium to High |
| force_majeure follow-up | Medium | Medium to High | Medium / partial | Low to Medium | Medium | Low |
| Formalize pause point | Low to Medium | Low | Low | Low | Medium | High |

## Why the test-infra track stands out

The Postgres-aligned test follow-up has the best current balance:

- it is **not blocked** by product semantics
- it improves confidence for later deprecation work
- it targets a known repo-level drift:
  - `backend/.env` uses Postgres
  - `backend/tests/conftest.py` still provisions SQLite
- queue, numbering, and concurrency behavior are especially sensitive to DB
  semantics

## Why OnlineDay continuation is not the best deterministic move

Although OnlineDay deprecation still has high long-term value, its remaining
live surfaces are now concentrated in routes and behaviors that are not purely
engineering problems:

- `open_day` / `close_day` are blocked by external/manual usage risk
- `next_ticket` is already on a `DEPRECATE_LATER` path
- the remaining board flags are blocked by product semantics

That means the highest-value parts of OnlineDay continuation are no longer
fully deterministic.

## Why docs consolidation is not chosen first

Docs consolidation is safe and useful, but it does not strengthen runtime
confidence. It should follow, not precede, the most meaningful deterministic
confidence upgrade.

## Why residue cleanup is not chosen first

Residue cleanup gives tidy wins, but it is now narrow and incremental:

- some residue is still protected by tests or file-path gates
- cleanup alone will not reduce the most important remaining architecture risk

## Why force_majeure follow-up is not chosen first

force_majeure is intentionally isolated and no longer blocks the main queue
track. Its remaining candidate corrections are valid, but not as leverage-rich
as reducing environment/test drift for the whole system.

## Why a formal pause point is not chosen first

A pause point is only the best move when no meaningful deterministic track
remains. That is not the current situation.
