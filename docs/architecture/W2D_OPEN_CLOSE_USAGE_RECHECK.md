## Summary

I rechecked the repository for direct and indirect consumers of:

- `POST /api/v1/appointments/open-day`
- `POST /api/v1/appointments/close`

Result:

- no confirmed live frontend caller for either legacy route was found
- no confirmed backend internal caller was found beyond the mounted route owners and a support mirror
- the current in-repo operational frontend flow uses a different route, `POST /api/v1/registrar/open-reception`
- therefore, there is still no confirmed in-repo runtime consumer of the exact legacy `open-day` / `close` routes

## Findings

| File / scope | Exact reference | Live/runtime | Direct or indirect consumer | Confidence |
| --- | --- | --- | --- | --- |
| `backend/app/api/v1/endpoints/appointments.py` | `open_day()` / `close_day()` mounted route owners | Yes | Route owners only, not downstream callers | High |
| `backend/app/services/appointments_api_service.py` | `open_day()` / `close_day()` service-mirror functions | No | Indirect mirror / architecture surface only | High |
| `backend/tests/characterization/test_open_close_day_characterization.py` | direct requests to `/api/v1/appointments/open-day` and `/api/v1/appointments/close` | No | Test-only consumer | High |
| `frontend/src/**` | no match for `/appointments/open-day`, `/appointments/close`, `open_day`, `close_day` | No | No direct frontend caller found | High |
| `backend/**` internal callers | no match for a runtime caller beyond route owner + service mirror | No | No confirmed backend internal caller found | Medium |
| `frontend/src/api/queue.js` | `openReceptionSlot()` -> `POST /registrar/open-reception` | Yes | Direct live frontend consumer of the newer operational flow, not of `open-day` | High |
| `frontend/src/hooks/useQueueManager.js` | `openReceptionForDoctor()` -> `openReceptionSlot(...)` | Yes | Indirect live frontend consumer of the newer operational flow | High |

## Interpretation

The repo does show a live operational concept for "open reception", but that concept has already moved to a newer route:

- `POST /api/v1/registrar/open-reception`

That lowers confidence that the legacy `open-day` route is still part of the current in-repo UI path.

For `close_day`, the recheck is even narrower:

- no frontend caller found
- no backend internal caller found
- only the mounted route owner, support mirror, and tests remain visible in-repo

## Conclusion

The exact legacy routes remain mounted, but this recheck does **not** confirm meaningful in-repo runtime usage for them.

What it does confirm:

- the routes still exist and are publicly mounted for admin users
- the repo still models the operational concept elsewhere
- any remaining real usage risk is now more likely to come from manual or external workflows than from current in-repo code callers
