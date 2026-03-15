# W2D board new endpoint migration strategy

## Coexistence rule

During transition:

- keep legacy `/board/state` unchanged
- introduce the new adapter-backed endpoint separately
- migrate the frontend only after the new endpoint contract is explicit and
  test-covered

This first additive step is now complete:

- `GET /api/v1/display/boards/{board_key}/state` exists
- it is metadata-only v1
- it is not yet used by the live UI

## Recommended rollout sequence

### Phase 1

- prepare endpoint contract
- add a thin endpoint skeleton around `BoardStateReadAdapter`
- no live UI switch

Status:

- done

### Phase 2

- verify adapter output with targeted endpoint tests
- validate metadata payload against display-config fixtures and expectations
- keep legacy route untouched

Status:

- started by the mounted skeleton tests

### Phase 3

- migrate the board UI to the new endpoint for display metadata only
- continue using existing sources for counters and queue activity

### Phase 4

- evaluate whether any legacy `/board/state` consumer remains
- decide whether to retire the legacy route later or keep it as a separate
  legacy island

## Rollout and rollback

### Rollout

- additive route introduction only
- frontend switch in a separate staged slice
- no dependency on in-place legacy replacement

### Rollback

- revert the frontend to old fallback/default behavior
- leave legacy `/board/state` untouched
- keep the additive endpoint unused if necessary

## Should dual-read be used?

Not as a strict legacy-vs-new parity strategy.

Reason:

- the legacy route and the new endpoint intentionally serve different contract
  shapes

What is still useful:

- side-by-side verification at the adapter/output level
- targeted snapshot tests for the new endpoint contract
- UI smoke verification after frontend migration

## Why coexistence is safe

The new endpoint does not mutate:

- legacy request shape
- legacy response shape
- OnlineDay ownership

That keeps the change bounded and reversible.
