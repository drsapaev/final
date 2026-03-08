# Wave 2C Registrar Batch Decision Matrix

Date: 2026-03-08
Mode: analysis-first, docs-only

| Area | Current runtime behavior | Target contract | Conflict severity | What must happen first |
|---|---|---|---|---|
| Duplicate gate on `waiting/called` | Reuses existing row | Reuse existing row | None | Nothing |
| Duplicate gate on `diagnostics` | Creates new `waiting` row | Reuse existing active row | High | Behavior correction |
| Duplicate gate on `in_service` | Code would allow new row | Reuse existing active row | Medium | Behavior correction or added characterization if desired |
| Same-specialist multi-service batch | One row per specialist/day | One row per specialist/day | None | Nothing |
| Different specialists in one batch | Separate rows per specialist/day | Separate rows per specialist/day | None | Nothing |
| Source passthrough | Preserves request source on create | Preserve request source on create | None | Nothing |
| Number allocation path | Legacy SSOT allocator through `queue_service` | Same allocator semantics for now | None | Nothing before correction |
| Runtime owner | Router-level ORM flow | Service-owned orchestration before boundary migration | Medium | Seam extraction after behavior correction |

## Main Conclusion

The batch-only contract is clarified enough to stop debating claim shape.

The first remaining blocker is not claim ambiguity anymore. It is a concrete
behavior drift in the active-entry duplicate gate.

## Decision

Behavior correction is required **before** boundary migration.
