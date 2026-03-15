# W2D Next Execution Unit After appointments.stats Review

## Recommended next step

`narrow appointments.stats deprecation-prep slice`

## Why this is the safest next step

- the route is mounted, so immediate removal is still too abrupt
- the route is read-only, so deprecation prep is lower risk than the blocked
  OnlineDay write/admin surfaces
- the route appears duplicative and currently lacks a confirmed live in-repo
  consumer

## What that slice should do

The next bounded slice should prepare retirement safely, for example by:

- making the route's duplicate/legacy status explicit in docs and contracts
- deciding whether OpenAPI deprecation signaling is appropriate
- tightening consumer evidence one more step before any actual route removal

## Why not jump back to `open_day` / `close_day`

Those routes remain blocked by possible manual/external usage.

## Why not start with support-only cleanup instead

That would give less architectural value than reducing one more still-mounted
OnlineDay public surface.
