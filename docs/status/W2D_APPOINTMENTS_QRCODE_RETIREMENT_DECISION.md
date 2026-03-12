# W2D Appointments QRCode Retirement Decision

Date: 2026-03-11
Mode: docs-only review

## Verdict

`READY_FOR_DEPRECATION_PREP`

## Why

The route:

- is still mounted
- is read-only
- does not own `OnlineDay` writes
- has no confirmed in-repo live consumer
- is already effectively classified as support-only in prior OnlineDay
  inventory docs

## Why not immediate removal

Immediate removal would be stronger than the current evidence allows.

Because the route is still mounted, low-confidence external/manual usage cannot
be ruled out fully.

## Practical interpretation

The safest next engineering step is:

- do not remove the route yet
- do not modernize it into a new SSOT path
- move it into an explicit deprecation-prep state

That keeps blast radius low while continuing to shrink the legacy surface area
honestly.
