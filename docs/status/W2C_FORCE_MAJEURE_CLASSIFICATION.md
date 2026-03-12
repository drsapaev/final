# Wave 2C Force Majeure Classification

Date: 2026-03-09
Mode: characterization-first
Classification: `B) exceptional transfer-domain`

## Why

- The production-relevant allocator path is not a standard queue join/create.
- It creates a new tomorrow row, cancels the old row, assigns explicit priority,
  and resets queue time.
- Cancellation flow is tightly coupled to refund/deposit handling.

## What It Is Not

- not a thin normal boundary caller
- not just a legacy dead island
- not a pure policy-free row creation path
