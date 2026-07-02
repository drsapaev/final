# VPS Proof Track Go / No-Go

## Must be proven first
- VPS staging deploy from the current host kit
- cutover and rollback rehearsal
- load / soak budgets on the promotion path
- observability SLA review loop
- tenant isolation on the promoted contour

## What can wait
- broad runtime implementation
- non-essential doc polishing
- any historical recovery cleanup

## Should the next track start immediately?
YES, but as a proof-only track

## Do we need implementation first?
NO, unless a rehearsal exposes a tiny blocking gap that can be fixed without expanding scope

## Final guidance
- Start the `VPS Promotion Proof Track` now.
- Keep the track narrow, evidence-driven, and operationally focused.

