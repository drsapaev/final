# W2D Open / Close Semantic Options

This document compares realistic target semantics for `open_day` and `close_day`.

## Option A — Keep As Operational Admin Lifecycle Actions

Meaning:

- retain the actions as explicit admin controls for a department/day intake window
- keep them outside the SSOT queue allocator domain

Pros:

- matches current practical behavior more honestly
- keeps compatibility with possible external/manual admin usage
- avoids forcing department/day controls into specialist-based SSOT semantics

Risks:

- preserves a small but live legacy operational subsystem
- requires clearer ownership and less ambiguous naming over time

Compatibility impact:

- low to medium

Rollout complexity:

- medium

## Option B — Replace With SSOT-Backed Admin Adapter

Meaning:

- keep the admin intent, but move execution onto a dedicated adapter around SSOT-compatible constructs

Pros:

- aligns better with the post-W2C architecture
- could reduce dependency on OnlineDay eventually

Risks:

- no clean SSOT equivalent exists yet
- department/day semantics do not map directly to specialist/day queues
- likely requires more design than a narrow follow-up slice

Compatibility impact:

- medium to high

Rollout complexity:

- high

## Option C — Deprecate Later As OnlineDay-Only Legacy Lifecycle

Meaning:

- freeze the routes as legacy operational behavior
- plan later retirement after confirming lack of real usage

Pros:

- low immediate risk
- acknowledges current isolation honestly

Risks:

- leaves live mutable legacy behavior in place longer
- does not reduce OnlineDay operational scope by itself

Compatibility impact:

- low now, medium later

Rollout complexity:

- low now, medium later

## Option D — Retire If No Real Consumer Remains

Meaning:

- if operational/manual usage is not real anymore, remove the routes instead of replacing them

Pros:

- strongest legacy reduction outcome
- simplifies OnlineDay deprecation path

Risks:

- unsafe unless external/manual usage is truly ruled out
- current runtime asymmetry should be characterized before retirement decisions

Compatibility impact:

- high if usage still exists

Rollout complexity:

- medium to high
