# Wave 2C Active Entry Contract

Date: 2026-03-07
Mode: analysis-first, docs-only

## Purpose

This document defines the canonical meaning of an "active queue entry" for the
future queue domain contract.

It does not rewrite current runtime behavior. It defines the target contract
that later migration slices should converge toward.

## Current Runtime Status Vocabulary

### Canonical queue-row statuses already present in the model

- `waiting`
- `called`
- `in_service`
- `diagnostics`
- `served`
- `incomplete`
- `no_show`
- `cancelled`
- `rescheduled`

### Runtime aliases and drift values

- `in_progress` -> `in_service`
- `completed` -> `served`
- `canceled` -> `cancelled`

## Canonical Active Definition

For queue-domain purposes, an entry is **active** if it still owns a live place
in the queue or is still being processed as part of that same queue visit.

### Canonical active statuses

- `waiting`
- `called`
- `in_service`
- `diagnostics`

### Canonical inactive statuses

- `served`
- `cancelled`
- `no_show`
- `incomplete`
- `rescheduled`

## Why This Set Is Proposed

### `waiting`

The patient is still in the line.

### `called`

The patient has an allocated live place and may still return to flow transitions
such as `in_service`, `diagnostics`, `no_show`, or `served`.

### `in_service`

The patient is no longer merely waiting, but the queue entry still represents a
live visit in progress.

### `diagnostics`

The patient remains part of the same queue lifecycle even if temporarily out of
the ordinary waiting list.

## Why The Others Are Inactive

### `served`

Terminal outcome for queue ownership.

### `cancelled`

Queue ownership ended.

### `no_show`

Inactive by default, even though restore flows may later reactivate it.

### `incomplete`

Inactive terminal-or-paused outcome from the allocator perspective. A later
reopen should be explicit, not implicit.

### `rescheduled`

The current queue row no longer represents an active claim in the current queue.

## Alias Mapping Contract

| Raw runtime value | Canonical interpretation |
|---|---|
| `in_progress` | `in_service` |
| `completed` | `served` |
| `canceled` | `cancelled` |

## Impact On Duplicate Policy

The proposed domain rule is:

an existing **active** queue entry blocks a new ticket allocation in the same
queue/day for the same identity, unless an explicit override contract applies.

That means the future duplicate-policy owner should evaluate duplicates against:

- `waiting`
- `called`
- `in_service`
- `diagnostics`

not only the narrower current runtime subset `waiting/called`.

## Impact On Other Read Models

This contract does **not** require every read model to use the same subset.

Specialized derived subsets may continue to exist, for example:

- position-visible entries
- reorder-active entries
- capacity-counted entries
- session-reuse entries

But those subsets should derive from the canonical state model, not define the
domain meaning of "active" on their own.

## Compatibility Note

Current runtime still uses narrower subsets in some places:

- duplicate checks: `waiting`, `called`
- queue limits / auto-close counts: `waiting`, `called`
- reorder: `waiting`, `called`
- session reuse: `waiting`, `called`, `in_service`
- position views: `waiting`, `called`, `in_service`, `diagnostics`

This document does not claim the runtime is already unified. It defines the
target contract that later migration steps should explicitly adopt.
