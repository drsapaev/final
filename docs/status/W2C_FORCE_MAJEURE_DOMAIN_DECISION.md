# Wave 2C Force Majeure Domain Decision

Date: 2026-03-09
Mode: contract-review
Decision: `B) exceptional-domain with its own contract`

## Why

- the family intentionally overrides ordinary queue fairness
- it intentionally resets `queue_time`
- it uses a distinct transfer source
- it couples queue behavior to transfer/cancel operational workflows
- cancellation flow is also refund/deposit-coupled

## Consequence

Force majeure should not be treated as a routine `QueueDomainService.allocate_ticket()`
migration candidate.

It can share infrastructure later, but it should be managed as a separate
exception-domain island with its own explicit contract.

## Isolation update

This decision is now operationally confirmed:

- the family has a compact mounted/live surface
- main queue-track families do not depend on force_majeure semantics
- next work should stay in an exceptional-domain follow-up track, not in the
  ordinary allocator-boundary rollout
