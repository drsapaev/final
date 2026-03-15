## Summary

Even though no confirmed in-repo frontend caller was found for the exact legacy `open-day` / `close` routes, the repository still contains strong operational signals that the underlying workflow may matter in practice.

## Strong Signals

| Signal source | Why it matters | Strength |
| --- | --- | --- |
| `docs/detail.md` | Repeatedly describes the registrar action "Открыть приём сейчас" as part of the real morning workflow, including button behavior and hotkey references | Strong |
| `docs/archives/detail.md` | Archived but detailed operational specification repeats the same registrar workflow and ties it to closing morning intake | Strong |
| `docs/QR_QUEUE_USER_MANUAL.md` | End-user / registrar manual still tells operators to press "Открыть приём" to close online intake | Strong |
| `backend/app/services/online_queue.py` comments | Code comments explicitly describe `OnlineDay.is_open` in terms of pressing "Открыть приём" | Strong |
| `backend/app/services/online_queue_new_api_service.py` comments | Newer queue flow still references the same operational button semantics from `detail.md` | Strong |
| `backend/app/services/registrar_integration_api_service.py` comments | The newer registrar-side route `/registrar/open-reception` is documented as the same "Открыть приём сейчас" operation | Strong |

## Medium Signals

| Signal source | Why it matters | Strength |
| --- | --- | --- |
| Mounted admin-only routes in `appointments.py` | Public admin routes that still exist are harder to treat as safely dormant, even without direct callers in repo | Medium |
| Prior architecture and replacement docs in `docs/architecture/*` and `docs/status/*` | Internal docs consistently still treat `open_day` / `close_day` as live legacy admin surfaces | Medium |

## Weak or Missing Signals

| Signal source | Finding | Strength |
| --- | --- | --- |
| `frontend/src/**` direct callers of `/appointments/open-day` or `/appointments/close` | None found | Weak / none |
| Backend internal runtime callers | None confirmed beyond the support mirror and tests | Weak / none |

## Interpretation

The signals are asymmetric:

- **route-specific code usage** for legacy `open-day` / `close` is weak
- **workflow-level operational meaning** for "open reception / close morning intake" is strong

That means the repository supports this conclusion:

- the operational concept still appears real
- but the exact legacy routes may no longer be the primary in-repo implementation path

## Operational Risk Implication

These signals are strong enough to keep us conservative.

They do **not** prove that the exact legacy routes are still used every day, but they do show that:

- operators are expected to understand this workflow
- documentation and code comments still assume it matters
- changing legacy semantics without external confirmation could still surprise manual or external users
