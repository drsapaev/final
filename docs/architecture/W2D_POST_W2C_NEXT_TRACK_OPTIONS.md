# W2D Post-W2C Next Track Options

This document compares realistic follow-up tracks after Wave 2C main architecture closure.

## Track A — OnlineDay Deprecation Path

Scope:
- Continue reducing the OnlineDay island directly.
- Move toward eventual removal of `online_queue.py`, `OnlineDay`, and legacy counter storage.

Pros:
- High long-term architectural payoff.
- Removes the last large legacy queue island.

Risks:
- Too broad while live mutating admin routes still lack a final contract direction.
- Can easily collapse multiple unresolved concerns into one cleanup effort.

Why not first:
- The live operational routes (`open-day`, `close-day`, `next-ticket`) still define whether the island can shrink safely.

## Track B — Board Finalization

Scope:
- Finish board-display migration by resolving `is_paused` / `is_closed`.

Pros:
- Small remaining legacy tail.
- Would make `DisplayBoardUnified` even less dependent on legacy `/board/state`.

Risks:
- Blocked by product semantics, not by missing engineering scaffolding.
- Could force invented ownership for ambiguous board flags.

Why not first:
- It is narrow and important, but it does not unlock the broader OnlineDay legacy reduction story.

## Track C — Operational Admin Routes Clarification

Scope:
- Clarify the future meaning and ownership of:
  - `POST /api/v1/appointments/open-day`
  - `POST /api/v1/appointments/close`
  - `POST /api/v1/queues/next-ticket`

Pros:
- Highest leverage for determining what remains of the OnlineDay island.
- Targets the remaining live mutating surfaces rather than read-only compatibility tails.
- Creates a clean boundary between operational admin behavior and SSOT queue behavior.

Risks:
- Some external/manual usage may exist.
- Could surface product/ops decisions around how manual day control should work in the future.

Why this is strong:
- This track decides whether the remaining OnlineDay island is a temporary compatibility shell or a durable operational subsystem.

## Track D — Legacy Websocket Cleanup

Scope:
- Revisit legacy `queue.update` payloads and any remaining dotted-event broadcast behavior.

Pros:
- Cleans up old real-time semantics.

Risks:
- External/manual consumer uncertainty.
- Lower leverage than the live admin routes that still mutate the legacy island.

Why not first:
- Better treated after operational endpoint meaning is clarified.

## Track E — Docs Consolidation + Dead Code Detection

Scope:
- Consolidate docs and continue support-only / stale cleanup.

Pros:
- Low risk.
- Keeps the repo tidy.

Risks:
- Limited architectural leverage.
- Does not resolve live legacy behavior.

Why not first:
- Valuable housekeeping, but not the highest-value architectural move after Wave 2C.

## Recommendation Summary

The strongest next architectural track is **Track C — Operational Admin Routes Clarification**.

Reason:
- It addresses the remaining live mutating OnlineDay surfaces.
- It directly determines how far OnlineDay deprecation can go.
- It avoids forcing unresolved board semantics (`is_paused`, `is_closed`) into an engineering-only track.
