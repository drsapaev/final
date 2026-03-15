# Wave 2D Deterministic Tails

Date: 2026-03-10  
Mode: analysis-first, docs-only

This document inventories the remaining post-W2C tracks that can still move
without first resolving product/business semantics.

## Inventory

| Track | What is already done | What remains | Blocked by semantics? | Expected architectural value | Expected implementation risk |
| --- | --- | --- | --- | --- | --- |
| OnlineDay deprecation continuation | OnlineDay isolated as a legacy island; dead routers removed; support mirrors mostly removed; `queues.stats` partially replaced; board-display mostly migrated off legacy | Live legacy admin surfaces still remain: `open_day`, `close_day`, `next_ticket`, legacy `/board/state`, plus final service/model retirement | **Yes, partially** | High if eventually completed, because it shrinks the last major legacy subsystem | High, because the remaining live surfaces now intersect ops/product semantics and external-usage risk |
| Test infrastructure / Postgres-aligned follow-up | Queue architecture is stabilized; many characterization tests now exist; production/dev uses Postgres while pytest still runs on SQLite | Inventory drift, identify queue-sensitive SQLite assumptions, define migration/prep path for more production-like verification | **No** | High, because it improves confidence for every later cleanup/deprecation step | Medium, if kept prep-first and characterization-first |
| Docs / architecture consolidation | W2C closure docs, W2D prep docs, and many targeted status docs already exist | Consolidate superseded status docs, simplify top-level architecture set, reduce drift and duplication | **No** | Medium, because it improves navigation and maintainability of decision history | Low |
| Support/test-only residue cleanup | Dead routers removed; support-only mirrors mostly cleaned; residue narrowed | Remaining retained artifacts such as `appointments_api_service.py`, stale docs references, and other test-only/support-only fragments | **No** | Medium-low, because it reduces maintenance noise and accidental confusion | Low to Medium, due to test/file-path dependencies |
| force_majeure follow-up | force_majeure isolated as exceptional-domain; local contract and follow-up track defined | Possible local corrections: duplicate gate, numbering monotonicity, pending-entry eligibility, priority-policy confirmation | **Yes, partially** | Medium, because it improves a contained exceptional path | Medium to High, because some candidate fixes still depend on business/policy clarification |
| Formalize pause point | Major architecture refactor is already closed; blocked tails are known and documented | Produce a consolidated blocked-tail register and freeze point for later work | **No** | Low to Medium, because it reduces ambiguity but does not materially improve runtime confidence | Low |

## Deterministic-tail interpretation

Among the remaining tracks, two are clearly deterministic and materially useful
without needing product sign-off first:

1. `Test infrastructure / Postgres-aligned follow-up`
2. `Docs / architecture consolidation`

`Support/test-only residue cleanup` is also deterministic, but it offers less
architectural leverage than the test-infra track.

## Non-deterministic or partially blocked tails

These tracks remain important, but they are not the best next deterministic
move:

- `OnlineDay deprecation continuation`
- `force_majeure follow-up`

Both now intersect semantics, external usage risk, or business-policy
confirmation.
