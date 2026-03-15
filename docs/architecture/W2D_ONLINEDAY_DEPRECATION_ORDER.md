# Wave 2D OnlineDay Deprecation Order

Date: 2026-03-09
Mode: analysis-first, docs-only

## Phase A: Dead / disabled cleanup candidates

Targets:

- `backend/app/api/v1/endpoints/online_queue.py`
- `backend/app/api/v1/endpoints/online_queue_legacy.py`
- `backend/app/crud/queue.py`

Execution update (2026-03-09):

- `backend/app/api/v1/endpoints/online_queue.py` removed
- `backend/app/api/v1/endpoints/online_queue_legacy.py` removed
- `backend/app/crud/queue.py` retained because `backend/app/api/v1/endpoints/mobile_api_extended.py`
  still imports it in live runtime

Prerequisites:

- grep/import verification that no mounted runtime path imports these files
- test/doc search for stale references

Risks:

- low; primary risk is removing something still referenced by tests or docs

Blockers:

- any hidden import discovered during cleanup verification

Expected artifacts / tests:

- narrow cleanup PR
- import/reference audit
- API smoke check confirming mounted routes unchanged

## Phase B: Support-only legacy mirrors

Targets:

- `backend/app/services/online_queue_api_service.py`
- `backend/app/services/appointments_api_service.py`
- `backend/app/services/board_api_service.py`
- `backend/app/services/queues_api_service.py`
- possibly mounted compatibility helper `appointments.qrcode_png()` if product no
  longer needs it

Prerequisites:

- caller verification proving live mounted endpoints do not route through these
  mirrors
- frontend/consumer check for `qrcode_png()`

Risks:

- medium; support-only mirrors can still be imported indirectly

Blockers:

- unresolved import usage
- unclear frontend or admin consumer dependency

Expected artifacts / tests:

- narrow cleanup PR or cleanup-prep PR
- import/reference characterization
- endpoint smoke checks for unaffected mounted surfaces

Execution update (2026-03-09):

- Removed:
  - `backend/app/services/online_queue_api_service.py`
  - `backend/app/services/board_api_service.py`
  - `backend/app/services/queues_api_service.py`
- Retained:
  - `backend/app/services/appointments_api_service.py`

Retention reason:

- `appointments_api_service.py` is not a mounted runtime owner, but the current
  service-boundary suite still treats it as a required repository artifact and
  fails if the file is absent.

## Phase C: Live mounted endpoint replacement preparation

Targets:

- `appointments.open_day()`
- `appointments.stats()`
- `appointments.close_day()`
- `queues.stats()`
- `queues.next_ticket()`
- `board.state()`

Prerequisites:

- explicit owner decision: replace vs retire
- characterization coverage for current mounted legacy behavior
- consumer map for board/stats/admin operations

Risks:

- high; these are still live operator-facing endpoints

Blockers:

- no replacement owner selected
- no consumer/UX migration plan

Expected artifacts / tests:

- replacement requirements
- endpoint characterization suite
- board/stats parity checks

## Phase D: Service / model deprecation

Targets:

- `backend/app/services/online_queue.py`
- `backend/app/models/online.py`

Prerequisites:

- all live mounted endpoints replaced or retired
- support-only mirrors already removed
- no remaining runtime dependency on `OnlineDay` state or `last_ticket`

Risks:

- high; removing these too early breaks all remaining legacy surfaces

Blockers:

- any live endpoint still reading or writing `OnlineDay`

Expected artifacts / tests:

- removal characterization
- migration/removal checklist
- rollback notes

## Phase E: Final removal

Targets:

- remaining OnlineDay schema/runtime ownership
- legacy docs/runbooks referencing live OnlineDay operations

Prerequisites:

- Phases A-D completed
- final verification that no mounted route or operator workflow depends on the
  legacy island

Risks:

- medium if previous phases were clean; high if hidden dependencies remain

Blockers:

- unresolved consumer dependency
- unresolved data-retention or audit requirement

Expected artifacts / tests:

- final cleanup PR
- removal smoke tests
- deprecation notice / release note

## Deprecation-order verdict

The safest order is strictly outside-in:

1. dead/disabled cleanup
2. support-only mirror cleanup
3. live endpoint replacement prep
4. service/model deprecation
5. final removal

Any plan that starts with `OnlineDay` model or `online_queue.py` removal is too
early.

After the first dead-cleanup slice, the revised interpretation is:

1. dead/disabled endpoint/module cleanup first
2. support-only mirror cleanup second
3. any retained legacy-adjacent helpers only after separate verification
4. live mounted endpoint replacement prep after that

After the support-cleanup slice, the revised interpretation is:

1. dead/disabled cleanup completed except for retained non-island helper `crud/queue.py`
2. support-only cleanup mostly completed
3. `appointments_api_service.py` remains as a legacy-adjacent architecture/test anchor
4. next safe step is live mounted endpoint replacement prep, not more blind support deletion
