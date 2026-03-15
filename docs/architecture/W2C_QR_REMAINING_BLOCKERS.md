# Wave 2C QR Remaining Blockers

Date: 2026-03-09
Mode: docs-only readiness review

## Blocker Matrix

| Blocker | Severity | Blocks migration | Narrow fix possible | Notes |
|---|---|---:|---:|---|
| QR create payload wider than current `create_entry` boundary (`birth_year`, `address`) | High | Yes | Yes | Current QR seam preserves fields that `queue_service.create_queue_entry(...)` does not write |
| QR create payload uses QR-local `services_json` / `service_codes_json` handoff shape | Medium | Yes | Yes | Needs an adapter or widened boundary call contract, but is localized |
| Raw SQL numbering assumptions remain inside QR seam | Medium | No | Yes | Important for later allocator redesign, not a blocker for compatibility migration prep |
| Missing canonical duplicate gate before additional-service create | Medium | No | Yes | Characterized runtime debt; can remain unchanged during a caller-only migration |
| `queue_session` reuse excludes `diagnostics` | Medium | No | Yes | Contract drift remains, but both current seam and legacy boundary path use the same helper |
| Source inheritance ambiguity | Low | No | Yes | Current rule is explicit enough: `entry.source or "online"` |
| QR token/session coupling | Low | No | No action needed for this slice | `full_update_online_entry()` is post-join and no longer depends on QR join-session token replay logic |

## Interpretation

The remaining blockers are now narrow and local.

This family is no longer blocked by:

- hidden allocator ownership
- broad QR join orchestration
- clinic-wide QR fan-out ambiguity

It is blocked only by the gap between the QR-local handoff payload and the
current compatibility boundary's supported `create_entry` shape.

## Migration Impact

If the next slice closes only the QR-local create payload gap, the family should
be able to perform a caller migration without:

- changing raw numbering behavior
- changing `queue_time` semantics
- changing source inheritance
- changing additional-service fan-out behavior
