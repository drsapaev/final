## Wave 2D Queue Postgres Harness Results

Date: 2026-03-10
Mode: pilot-first, evidence-based

## Commands used

SQLite baseline:

```powershell
cd backend
pytest tests/characterization/test_queue_allocator_characterization.py tests/characterization/test_queue_allocator_concurrency.py -q -c pytest.ini
```

Postgres pilot:

```powershell
cd backend
pytest tests/characterization/test_queue_allocator_characterization.py tests/characterization/test_queue_allocator_concurrency.py -q -c pytest.ini --db-backend=postgres
```

OpenAPI verification:

```powershell
cd backend
pytest tests/test_openapi_contract.py -q
```

SQLite confidence run:

```powershell
cd backend
pytest -q
```

## What the harness adds

- root test fixture layer now supports an opt-in `--db-backend=postgres`
- default path still uses the existing SQLite temp-file DB
- Postgres path creates an isolated temporary schema and runs the same pilot
  family against it

## Proven SQLite result

- SQLite pilot family: `7 passed`
- Full backend suite on default SQLite path after the schema fixes: `785 passed, 3 skipped`

This confirms the harness did not destabilize the current default path.

## Proven Postgres result

### Before the narrow schema fix

- Postgres pilot family did not reach allocator assertions
- it failed during schema bootstrap in `Base.metadata.create_all(...)`

Observed error:

- `doctor_treatment_templates.doctor_id` was declared as `VARCHAR(36)`
- it referenced `users.id`, which is `INTEGER`
- Postgres rejected this FK creation with `DatatypeMismatch`

### After the narrow schema fix

- Postgres pilot family now reaches runtime assertions
- the original metadata bootstrap blocker is resolved
- the pilot now surfaces follow-on drift in the tested family

## What drift was actually observed

### 1. Fixed real DB drift

Confirmed and fixed:

- the repository metadata previously contained a Postgres-invalid FK/type
  mismatch for `doctor_treatment_templates.doctor_id -> users.id`

### 2. Newly surfaced real DB drift

Observed after the first narrow fix:

- one pilot path now fails because `DailyQueue.specialist_id` strictly expects a
  `doctors.id`, while the test path supplies a user-oriented id
- one pilot path now fails because `queue_entries.source` is `VARCHAR(20)` but
  `force_majeure_transfer` is longer than 20 characters

### 3. Newly surfaced harness/session drift candidate

Observed after the fix:

- one concurrency pilot path now raises `InvalidRequestError` on
  `session.refresh(user)` under the Postgres lane, which looks like a
  session/transaction behavior difference rather than a proven schema mismatch

### 4. After the narrow source-length fix

Observed after the second narrow fix:

- the `queue_entries.source` length blocker is resolved
- SQLite pilot family remains green
- Postgres pilot family now advances to `5 passed, 2 failed`

Remaining honest blockers:

- `DailyQueue.specialist_id` strict FK enforcement surfaced in the registrar
  batch characterization path
- one concurrency path still shows the Postgres-lane `session.refresh(user)`
  issue

### 5. After the narrow specialist-FK fix

Observed after the third narrow fix:

- the `DailyQueue.specialist_id` ownership blocker is resolved
- SQLite pilot family remains green at `7 passed`
- the broader SQLite backend suite remains green at `785 passed, 3 skipped`
- Postgres pilot family now advances to `6 passed, 1 failed`

Remaining honest blocker:

- one concurrency path still raises `InvalidRequestError` on
  `session.refresh(user)` under the Postgres pilot lane

## Harness vs drift interpretation

These results are best classified as continued real DB drift discovery, not
only harness failure.

Why:

- the harness connected to Postgres successfully
- the temporary isolated schema was created successfully
- the pilot progressed from metadata bootstrap into runtime assertions
- the failures now expose concrete SQLite-vs-Postgres differences inside the
  queue-sensitive family

## Pilot strategy verdict

The pilot validates the chosen strategy:

- SQLite default lane remains safe
- Postgres lane surfaces concrete, actionable drift early
- broader fixture migration would have hidden this under a larger blast radius

## 6. After the narrow session-refresh / schema-routing fix

Observed after the fourth narrow fix:

- the remaining `session.refresh(user)` blocker was investigated to root cause
- the issue was not another application schema mismatch
- it was a Postgres pilot harness/session-lifecycle problem caused by
  inconsistent temporary-schema routing across pooled connections
- the concurrency setup helper was also made less refresh-dependent

What was changed:

- the pilot Postgres engine now pins `search_path` through startup options,
  connect hooks, and checkout hooks
- the concurrency helper now uses `flush()` plus captured ids instead of
  `refresh()` during setup

Results after the fix:

- SQLite pilot family: `7 passed`
- Postgres pilot family: `7 passed`
- OpenAPI verification: `10 passed`
- broader SQLite backend suite confidence run: `785 passed, 3 skipped`

Interpretation:

- the target pilot family now passes fully on both lanes
- this validates the dual-lane pilot strategy more strongly
- the last blocker in this family was a pilot harness/session-lifecycle issue,
  not another queue-domain or schema-domain drift

## 7. After extending the pilot to the open/close family

Observed during the next pilot extension:

- `backend/tests/characterization/test_open_close_day_characterization.py`
  ran successfully in the default SQLite lane
- the same family also ran successfully in the opt-in Postgres lane
- no additional harness changes were required

Results:

- SQLite open/close pilot family: `3 passed`
- Postgres open/close pilot family: `3 passed`
- OpenAPI verification: `10 passed`

Interpretation:

- the dual-lane pilot approach now works across more than one queue-sensitive
  family
- not every queue/legacy-sensitive family is currently blocked by DB drift
- the pilot is now strong enough to distinguish:
  - real schema drift
  - harness/session drift
  - stable legacy operational behavior with no DB-specific divergence

## 8. After extending the pilot to the queues.stats parity family

Observed during the next pilot extension:

- `backend/tests/characterization/test_queues_stats_parity_harness.py`
  ran successfully in the default SQLite lane
- the same family also ran successfully in the opt-in Postgres lane
- no additional harness changes were required

Results:

- SQLite queues.stats pilot family: `3 passed`
- Postgres queues.stats pilot family: `3 passed`
- OpenAPI verification: `10 passed`

Interpretation:

- the legacy-vs-SSOT parity family behaves consistently across both DB lanes
- no new DB-specific drift surfaced in this slice
- the pilot strategy is now validated on three queue-sensitive families with a
  mix of:
  - real drift discovery
  - harness issue discovery
  - stable no-drift confirmation

## 9. After extending the pilot to the board_state parity family

Observed during the next pilot extension:

- `backend/tests/characterization/test_board_state_parity_harness.py`
  ran successfully in the default SQLite lane
- the same family also ran successfully in the opt-in Postgres lane
- no additional harness changes were required

Results:

- SQLite board_state pilot family: `3 passed`
- Postgres board_state pilot family: `3 passed`
- OpenAPI verification: `10 passed`

Interpretation:

- legacy-vs-adapter board-state parity behaves consistently across both DB lanes
- no new DB-specific drift surfaced in this slice
- the pilot strategy is now validated on four queue-sensitive families with a
  clear mix of:
  - real schema drift discovery
  - harness/session drift discovery
  - stable no-drift confirmation

## 10. After extending the pilot to the force_majeure family

Observed during the next pilot extension:

- `backend/tests/characterization/test_force_majeure_allocator_characterization.py`
  ran successfully in the default SQLite lane
- the same family also ran successfully in the opt-in Postgres lane
- no additional harness changes were required

Results:

- SQLite force_majeure pilot family: `2 passed`
- Postgres force_majeure pilot family: `2 passed`
- OpenAPI verification: `10 passed`

Interpretation:

- the isolated exceptional-domain family behaves consistently across both DB
  lanes
- no new DB-specific drift surfaced in this slice
- the pilot strategy is now validated on five bounded queue-sensitive families
  with a clear mix of:
  - real schema drift discovery
  - harness/session drift discovery
  - stable no-drift confirmation

## 11. After extending the pilot to the confirmation concurrency family

Observed during the next pilot extension:

- `backend/tests/characterization/test_confirmation_split_flow_concurrency.py`
  ran successfully in the default SQLite lane
- the same family also ran successfully in the opt-in Postgres lane
- no additional harness changes were required

Results:

- SQLite confirmation pilot family: `2 passed`
- Postgres confirmation pilot family: `2 passed`
- OpenAPI verification: `10 passed`

Interpretation:

- the bounded confirmation concurrency family behaves consistently across both
  DB lanes
- no new DB-specific drift surfaced in this slice
- the pilot strategy is now validated on six bounded queue-sensitive families
  with a clear mix of:
  - real schema drift discovery
  - harness/session drift discovery
  - stable no-drift confirmation

## 12. After extending the pilot to the registrar batch concurrency family

Observed during the next pilot extension:

- `backend/tests/characterization/test_registrar_batch_allocator_concurrency.py`
  ran successfully in the default SQLite lane
- the same family also ran successfully in the opt-in Postgres lane
- no additional harness changes were required

Results:

- SQLite registrar-batch pilot family: `2 passed`
- Postgres registrar-batch pilot family: `2 passed`
- OpenAPI verification: `10 passed`

Interpretation:

- the bounded registrar-batch concurrency family behaves consistently across
  both DB lanes
- no new DB-specific drift surfaced in this slice
- the pilot strategy is now validated on seven bounded queue-sensitive
  families with a clear mix of:
  - real schema drift discovery
  - harness/session drift discovery
  - stable no-drift confirmation

## 13. After extending the pilot to the QR direct-SQL concurrency family

Observed during the next pilot extension:

- `backend/tests/characterization/test_qr_queue_direct_sql_concurrency.py`
  ran successfully in the default SQLite lane
- the same family also ran successfully in the opt-in Postgres lane
- no additional harness changes were required

Results:

- SQLite QR pilot family: `2 passed`
- Postgres QR pilot family: `2 passed`
- OpenAPI verification: `10 passed`

Interpretation:

- the bounded QR direct-SQL concurrency family behaves consistently across both
  DB lanes
- no new DB-specific drift surfaced in this slice
- the pilot strategy is now validated on eight bounded queue-sensitive
  families with a clear mix of:
  - real schema drift discovery
  - harness/session drift discovery
  - stable no-drift confirmation

## 14. After extending the pilot to the QR characterization family

Observed during the next pilot extension:

- `backend/tests/characterization/test_qr_queue_direct_sql_characterization.py`
  ran successfully in the default SQLite lane
- the same family did not go fully green in the opt-in Postgres lane
- no additional harness changes were required

Results:

- SQLite QR characterization family: `4 passed`
- Postgres QR characterization family: `3 passed, 1 failed`
- OpenAPI verification: `10 passed`

Interpretation:

- the pilot strategy again surfaced a real DB/schema issue instead of a harness
  issue
- the newly exposed blocker is a bounded `Service.service_code` length mismatch
  under strict Postgres enforcement
- this keeps validating the dual-lane approach as an honest detector of real
  drift, not just a green-path confirmation tool

## 15. After fixing the QR characterization `service_code` drift

Observed during the narrow follow-up fix:

- `Service.service_code` was widened so legitimate current runtime values could
  pass strict Postgres enforcement
- the SQLite QR characterization family stayed green
- the Postgres QR characterization family progressed past the old insert-time
  blocker

Results:

- narrow service-code schema test: `1 passed`
- SQLite QR characterization family: `4 passed`
- Postgres QR characterization family: `3 passed, 1 failed`
- OpenAPI verification: `10 passed`
- broader SQLite backend suite confidence run: `786 passed, 3 skipped`

Interpretation:

- the original `service_code` length mismatch is fixed
- the pilot now exposes the next honest blocker in the same family:
  timezone-aware `queue_time` round-trip behavior under Postgres
- this remains a real DB-lane drift signal, not a harness/session problem

## 16. After fixing the QR characterization `queue_time` round-trip drift

Observed during the next narrow follow-up fix:

- the QR characterization family kept its existing SQLite lane green
- the Postgres lane no longer failed on the `queue_time` preservation assertion
- the fix stayed inside the characterization family and did not require runtime
  changes or a broader fixture rewrite

Results:

- SQLite QR characterization family: `4 passed`
- Postgres QR characterization family: `4 passed`
- OpenAPI verification: `10 passed`

Interpretation:

- the `queue_time` issue was expectation drift in the characterization test,
  not a new application schema defect
- SQLite returned a naive `datetime` while Postgres returned an aware
  `datetime` for the same timezone-aware column semantics
- after narrowing the assertion to preserved wall-clock value, the family is
  now green in both DB lanes
- the pilot strategy remains strongly validated and can continue to the next
  bounded family

## 17. After adding the shared `postgres_pilot` marker layer

Observed during the marker operationalization slice:

- a single `pytest` marker was added for the validated pilot families
- the aggregated SQLite marker lane ran green
- the aggregated Postgres marker lane progressed safely and surfaced a new
  bounded confirmation-family drift

Results:

- SQLite marker lane: `28 passed, 761 deselected`
- Postgres marker lane: `26 passed, 2 failed, 761 deselected`
- OpenAPI verification: `10 passed`

Interpretation:

- the marker layer itself is successful
- the newly surfaced blocker is not a marker/harness problem
- the next honest drift appears to be `Visit.status` length vs
  `pending_confirmation` in the confirmation family
- this further validates the pilot strategy as a reusable detector of real
  Postgres-enforced drift

## 18. After fixing the `Visit.status` length drift

Observed during the next narrow follow-up fix:

- `Visit.status` was widened to fit the already used legitimate runtime value
  `pending_confirmation`
- the SQLite marker lane stayed green
- the Postgres marker lane progressed beyond the old confirmation-family schema
  blocker

Results:

- narrow visit-status schema test: `1 passed`
- SQLite marker lane: `28 passed, 762 deselected`
- Postgres marker lane: `27 passed, 1 failed, 762 deselected`
- OpenAPI verification: `10 passed`

Interpretation:

- the `Visit.status` mismatch was a real Postgres-enforced schema drift
- the marker layer remains correct and useful
- the next honest blocker is no longer schema-length related
- the newly exposed issue is a datetime-awareness comparison mismatch in the
  confirmation family (`datetime.utcnow()` vs aware `confirmation_expires_at`)

## 19. After fixing the confirmation datetime-awareness drift

Observed during the next narrow follow-up fix:

- the confirmation domain now writes and compares its confirmation datetimes
  using a local UTC-aware helper
- the SQLite marker lane stayed green
- the Postgres marker lane progressed beyond the old confirmation-family
  naive-vs-aware datetime blocker

Results:

- narrow confirmation datetime test: `2 passed`
- SQLite marker lane: `28 passed, 764 deselected`
- Postgres marker lane: `28 passed, 764 deselected`
- OpenAPI verification: `10 passed`

Interpretation:

- the confirmation-family issue was a real runtime datetime-handling drift
  exposed by Postgres
- it was resolved without broad fixture churn or a global datetime refactor
- the aggregated pilot marker lane is now green in both DB lanes
- the safest next step shifts from bounded drift cleanup to dedicated CI
  wiring for `postgres_pilot`
