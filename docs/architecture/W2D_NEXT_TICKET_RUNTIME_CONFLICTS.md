# W2D next_ticket Runtime Conflicts

## What already matches the recommended direction

Current runtime already matches these statements:

- it is not a SSOT queue-entry lifecycle action
- it behaves like legacy ticket issuance
- it lives inside the OnlineDay island
- its downstream effects are mainly board/stats oriented

These are not bugs. They are faithful legacy behavior.

## What conflicts with the target direction

### 1. Route naming suggests queue progression

Current runtime:

- `next_ticket`

Target meaning:

- operational ticket issuance or eventual retirement

Conflict type:

- naming drift

### 2. Mounted public route still looks like part of active queue API

Current runtime:

- route is still mounted under `/api/v1/queues/*`

Target direction:

- not a future main-track queue action

Conflict type:

- legacy exposure drift

### 3. No confirmed in-repo consumer, but route still emits board-visible side effects

Current runtime:

- no direct caller found in repo
- route still mutates stats read by board/stats surfaces

Target direction:

- either deprecate later or isolate as explicit operational action

Conflict type:

- unresolved usage/ownership, not a direct code bug

### 4. No clean SSOT owner exists

Current runtime:

- OnlineDay + Setting counters own behavior

Target direction:

- either no survival
- or explicit admin adapter ownership

Conflict type:

- intentional legacy behavior that becomes a blocker for future change

## What would need to happen before any code change

Before any replacement or retirement work:

1. confirm whether any manual/external consumer still depends on the route
2. decide whether the action survives at all
3. if it survives, confirm operational owner and naming
4. only then choose adapter-prep or deprecation-prep

## Conflict summary

The current blockers are mostly not bugs.

They are:

- legacy naming drift
- legacy exposure still mounted
- unresolved product/operations ownership

That is why contract review is the right stage before code work.
