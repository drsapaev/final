# Wave 2C OnlineDay Live vs Dead Map

Date: 2026-03-09
Mode: analysis-first, docs-only

| File | Function / endpoint | Category | Why live or dead | Cleanup-later candidate |
|---|---|---|---|---|
| `backend/app/api/v1/endpoints/appointments.py` | `open_day()` | `LIVE_MOUNTED_LEGACY` | Still mounted admin path for legacy day-open state | Yes |
| `backend/app/api/v1/endpoints/appointments.py` | `stats()` | `LIVE_MOUNTED_LEGACY` | Still mounted stats path over legacy counters | Yes |
| `backend/app/api/v1/endpoints/appointments.py` | `close_day()` | `LIVE_MOUNTED_LEGACY` | Still mounted admin path for legacy day-close state | Yes |
| `backend/app/api/v1/endpoints/appointments.py` | `qrcode_png()` | `LEGACY_SUPPORT_ONLY` | Mounted compatibility payload, but does not own OnlineDay writes | Yes |
| `backend/app/api/v1/endpoints/queues.py` | `stats()` | `LIVE_MOUNTED_LEGACY` | Still mounted read path for legacy counters | Yes |
| `backend/app/api/v1/endpoints/queues.py` | `next_ticket()` | `LIVE_MOUNTED_LEGACY` | Only live mounted legacy allocator path | Yes |
| `backend/app/api/v1/endpoints/board.py` | `board_state()` | `LIVE_MOUNTED_LEGACY` | Mounted board read model over legacy counters | Yes |
| `backend/app/services/online_queue.py` | `get_or_create_day()` / `load_stats()` / `issue_next_ticket()` | `LIVE_MOUNTED_LEGACY` | Shared runtime owner behind mounted OnlineDay endpoints | Yes |
| `backend/app/api/v1/endpoints/online_queue.py` | `/online-queue/*` and `join_online_queue()` | `DEAD_OR_DISABLED` | Router is explicitly disabled in `api.py` | Yes |
| `backend/app/services/online_queue_api_service.py` | legacy online queue service mirror | `LEGACY_SUPPORT_ONLY` | Duplicate mirror for disabled router | Yes |
| `backend/app/services/appointments_api_service.py` | legacy queue admin mirror | `LEGACY_SUPPORT_ONLY` | Duplicate service mirror, not runtime owner | Yes |
| `backend/app/services/board_api_service.py` | legacy board mirror | `LEGACY_SUPPORT_ONLY` | Duplicate service mirror, not runtime owner | Yes |
| `backend/app/services/queues_api_service.py` | legacy queue mirror | `LEGACY_SUPPORT_ONLY` | Duplicate service mirror, not runtime owner | Yes |
| `backend/app/crud/queue.py` | stale counter helper functions | `DEAD_OR_DISABLED` | No active runtime caller found in current mounted OnlineDay surface | Yes |
| `backend/app/api/v1/endpoints/online_queue_legacy.py` | QR-based legacy aliases | `DEAD_OR_DISABLED` | Unmounted and delegates to QR, not to OnlineDay | Yes |

## Map verdict

The OnlineDay island still has a small live mounted core, but most surrounding
service mirrors and legacy aliases are support-only or dead/disabled cleanup
candidates.
