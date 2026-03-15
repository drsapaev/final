# W2D Open / Close Consumers

This audit checks who currently calls or depends on the mounted legacy routes:

- `POST /api/v1/appointments/open-day`
- `POST /api/v1/appointments/close`

## Confirmed Consumers

| Consumer | File | Mounted / live | Confirmed current use | Expected behavior | Migration risk |
| --- | --- | --- | --- | --- | --- |
| Legacy route itself | `backend/app/api/v1/endpoints/appointments.py` | Yes | Yes | Admin-only mutation of OnlineDay legacy state | High |
| Support mirror | `backend/app/services/appointments_api_service.py` | No | No as runtime owner | Architecture/service mirror of the same routes | Low |

## Not Confirmed In Repo

The following were checked and no confirmed in-repo caller was found:

- frontend pages
- admin/settings pages
- kiosk/display pages
- mobile/api wrappers
- backend internal callers beyond the mounted route itself

## External / Manual Usage Risk

External or manual usage cannot be ruled out because:

- both routes remain mounted
- both are admin-facing
- they mutate visible legacy department/day state

So even without an in-repo caller, compatibility risk is still real.
