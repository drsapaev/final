# W2D Post-W2C Legacy Classification

This document classifies each remaining post-W2C legacy surface by the kind of work it still requires.

## Classification Matrix

| Surface | Classification | Reasoning |
| --- | --- | --- |
| `GET /api/v1/board/state` | `LEGACY ISLAND (KEEP FOR NOW)` | The route is still mounted and intentionally left unchanged during staged board migration. It is no longer the preferred target contract, but it remains a compatibility surface until the board-display migration is fully settled. |
| `is_paused` / `is_closed` board flags | `PRODUCT / BUSINESS DECISION` | The blocker is no longer wiring or parity. The unresolved issue is what these fields should mean and who should own them. |
| `is_open` / `start_number` compatibility fields in `GET /api/v1/queues/stats` | `LEGACY ISLAND (KEEP FOR NOW)` | These fields are intentionally still legacy-backed while strict counters are already SSOT-backed. They can stay isolated until a later compatibility decision is made. |
| `POST /api/v1/queues/next-ticket` | `CONTRACT CLARIFICATION` | The route has a legacy meaning ("issue next department/day ticket"), not queue progression. Its long-term direction is already leaning toward deprecate-later, but a safe path still depends on confirming operational ownership and potential external usage. |
| `POST /api/v1/appointments/open-day` | `CONTRACT CLARIFICATION` | This is a live mutating admin route with no place in the main SSOT allocator track, but it may still survive as an operational action. Its future contract is not yet decided. |
| `POST /api/v1/appointments/close` | `CONTRACT CLARIFICATION` | Same as `open-day`: it is a live operational surface, but it is not yet clear whether it should survive as an admin action or be retired. |
| `backend/app/services/online_queue.py` | `LEGACY ISLAND (KEEP FOR NOW)` | It is still the runtime owner for the remaining OnlineDay behavior, so it cannot be treated as safe cleanup yet. |
| `backend/app/models/online.py::OnlineDay` | `LEGACY ISLAND (KEEP FOR NOW)` | The model still underpins the live legacy admin surfaces, so it remains an isolated island rather than cleanup material. |
| `Setting(category="queue")` counter keys | `LEGACY ISLAND (KEEP FOR NOW)` | These keys are still the mutable storage for the live OnlineDay behavior. Cleanup before route/contract decisions would be premature. |
| Legacy `queue.update` websocket fragment | `LEGACY ISLAND (KEEP FOR NOW)` | The payload is legacy-only and no longer part of the main queue track, but it may still matter for external/manual compatibility. |
| `backend/app/services/appointments_api_service.py` | `ENGINEERING CLEANUP` | This file is not a live runtime owner. It remains only because of the architecture/test surface and can later be revisited as safe cleanup. |

## Why These Buckets

- `ENGINEERING CLEANUP` is reserved for support-only residue that no longer owns live behavior.
- `CONTRACT CLARIFICATION` means the surface is still live and mounted, but the main unresolved question is "what should this action mean in the target system?"
- `PRODUCT / BUSINESS DECISION` means further progress would require inventing semantics, not clarifying or refactoring existing ones.
- `LEGACY ISLAND (KEEP FOR NOW)` means the surface is already isolated enough that it can stay in place temporarily without distorting the main architecture.
