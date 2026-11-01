# Registrar frontend — cumulative code-review ledger

> **Status:** FIVE-GROUP SOURCE INVENTORY COMPLETE / reproduction and triage pending. Documentation-only; not a release or approval report.
> **Started:** 2026-10-29 (Asia/Tashkent). **Repository:** `drsapaev/final`.
> **Baseline:** `main` at `9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1`.
> **Review type:** source inspection via GitHub file reads. **No runtime or automated tests were executed for these findings.**
> **Purpose:** retain every actionable review finding with source evidence, reproduce/verify it, and agree on a safe remediation sequence **after** the review inventory is complete.

## Execution boundary

- Mode: `direct_execute` for **one narrow, documentation-only review-ledger change**. No queue/clinical/payment behavior is modified.
- Authorized write scope: **this Markdown document only** on the dedicated audit branch; review evidence is read-only.
- Excluded: application source and tests, backend, migrations, configuration, production, deployments, live data, merges, and changes to queue ownership/fairness.
- Stop point: do not implement fixes in this audit PR. Reassess ownership and run the repository-mandated gate(s) before any later implementation PR involving queue/clinical/payment contracts.
- Validation for this documentation change: fetch the committed file and inspect the PR diff. CI and runtime tests remain unexecuted until explicitly checked; do not infer a green build.

## Status and severity legend

- `SOURCE-OBSERVED`: the described code path exists in the frozen baseline.
- `REPRO-PENDING`: an end-to-end or focused regression test still must demonstrate the user-visible effect.
- `CONFIRMED`: focused failing test or equivalent verified reproduction; **none yet**.
- `RESOLVED`: regression is fixed with tests and reviewed in a **separate fix PR**; no entries resolved yet.
- Severity P0–P3 is **provisional** until verification and triage; no P0/P1 demonstrated during this first pass.

## Findings index

| ID | Severity (provisional) | Area | Source observation | Status | Proposed fix/test batch |
| --- | --- | --- | --- | --- | --- |
| REG-FE-001 | P2 | Worklist row activation | Click/keyboard row activation invokes a logger-only callback rather than record preview | SOURCE-OBSERVED / REPRO-PENDING | Batch A: table interaction |
| REG-FE-002 | P2 | All-departments search | Search results omit the service-normalization step present in unfiltered results | SOURCE-OBSERVED / REPRO-PENDING | Batch B: pure worklist presentation |
| REG-FE-003 | P3 | Localization | `filteredAppointments` memo uses a translated fallback but does not depend on it | SOURCE-OBSERVED / REPRO-PENDING | Batch B: pure worklist presentation |
| REG-FE-004 | P2 | Welcome quick filters | Queue-status filters `queued`/`paid_pending` exclude backend `waiting` or payment-pending records | SOURCE-OBSERVED / REPRO-PENDING | Batch C: filter semantics |
| REG-FE-005 | P2 | URL date and worklist | Changing `?date` while mounted does not directly reload when calendar is closed; worklist heading still says today | SOURCE-OBSERVED / REPRO-PENDING | Batch D: date lifecycle |
| REG-FE-006 | P2 | Welcome actions | `in_cabinet`/`complete` commands lack confirmations present in the main table | SOURCE-OBSERVED / REPRO-PENDING | Batch A: action consistency |
| REG-FE-007 | P2 | Rate-limit handling | HTTP 429 returns without failure/stale state; tests explicitly pin a `loading=false`/`dataSource=loading` quirk | SOURCE-OBSERVED / REPRO-PENDING | Batch D: fetch state |
| REG-FE-008 | P2 | Refresh feedback | Welcome manual refresh announces success synchronously, before fetch outcome | SOURCE-OBSERVED / REPRO-PENDING | Batch D: fetch feedback |
| REG-FE-009 | P2 | Reschedule presentation | Optimistic deletion compares IDs from different record namespaces, potentially hiding an unrelated row | SOURCE-OBSERVED / REPRO-PENDING | Batch E: reschedule UI |
| REG-FE-010 | P2 | Existing patient selected in create mode | Form changes to existing patient profile are not sent to patient update API on create path | SOURCE-OBSERVED / REPRO-PENDING | Batch F: patient identity/profile UX |
| REG-FE-011 | P2 | Partial patient save before edit | `updatePatient` can commit changes before later queue/edit-delta failure | SOURCE-OBSERVED / REPRO-PENDING | Batch G: patient/visit atomicity |
| REG-FE-012 | P2 | Date-aware service catalogue | Older async service response can overwrite newer catalogue and rehydrate current cart | SOURCE-OBSERVED / REPRO-PENDING | Batch H: wizard data loading |
| REG-FE-013 | P2 | Wizard diagnostic privacy | Direct patient-phone string and `fio` object field can pass through development logger | SOURCE-OBSERVED / REPRO-PENDING | Batch I: privacy guard |
| REG-FE-014 | P2 | Context action acknowledgement | Context menu emits success for status changes even when the action returned null after failure | SOURCE-OBSERVED / REPRO-PENDING | Batch J: action feedback |
| REG-FE-015 | P2 | Partial batch status mutations | A partial server-side success yields an error but no worklist refresh/reconciliation | SOURCE-OBSERVED / REPRO-PENDING | Batch J: action feedback |
| REG-FE-016 | P3 | Cart visit forecast | Wizard banner counts distinct doctor IDs, while the payload groups by resource tag and appointment time too | SOURCE-OBSERVED / REPRO-PENDING | Batch K: cart summary |
| REG-FE-017 | P2 | Cancellation dialog handoff | Null/partial cancellation response can still resolve callback and trigger success/close | SOURCE-OBSERVED / REPRO-PENDING | Batch L: cancellation result contract |
| REG-FE-018 | P2 | Post-wizard reconciliation | Intended retry does not run for swallowed network/429/reference-data failures | SOURCE-OBSERVED / REPRO-PENDING | Batch M: post-save data lifecycle |
| REG-FE-019 | P3 | Wizard success feedback | Wizard and panel both trigger react-toastify success notifications for the same save | SOURCE-OBSERVED / REPRO-PENDING | Batch N: toast ownership |
| REG-FE-020 | P2 | Concurrent request tracking | Superseded request clears shared in-flight guard while newer queue load is still pending | SOURCE-OBSERVED / REPRO-PENDING | Batch O: request lifecycle |
| REG-FE-021 | P2 | Auto-refresh vs modal state | Timer snapshots other dialog flags at effect setup and does not react to their open/close changes | SOURCE-OBSERVED / REPRO-PENDING | Batch O: refresh lifecycle |
| REG-FE-022 | P2 | Synthetic queue number/active indicator | Adapter always creates a queue_numbers entry; a visit without a linked DailyQueue can appear to have an active queue | SOURCE-OBSERVED / REPRO-PENDING | Batch P: queue DTO truth |
| REG-FE-023 | P2 | Schedule-next dead control | Registrar context-menu schedule_next is shown but neither table nor menu action router handles it | SOURCE-OBSERVED / REPRO-PENDING | Batch Q: action exposure/wiring |
| REG-FE-024 | P2 | Aggregated action visibility | Context menu ignores grouped_records.available_actions and hides backend-permitted non-payment actions | SOURCE-OBSERVED / REPRO-PENDING | Batch Q: action exposure/wiring |
| REG-FE-025 | P2 | Force majeure target identity | Row action selects specialist_id from legacy doctor fields, not backend queue-owner scope, for mass queue transfer/cancel | CONFIRMED / FIX-IN-REVIEW — Draft PR #3809 (fail-first RED→GREEN, CI green, review pending) | Batch R: force-majeure owner boundary |
| REG-FE-026 | P3 | Context-menu reschedule visibility | Menu checks missing can_reschedule/reschedule signal on canonical registrar queue rows while inline reschedule remains accessible | SOURCE-OBSERVED / REPRO-PENDING | Batch Q: action exposure/wiring |
| REG-FE-027 | P2 | Welcome morning doctor summary | Doctor groups use absent legacy IDs and count rows, not distinct patients | SOURCE-OBSERVED / REPRO-PENDING | Batch S: Welcome summary |
| REG-FE-028 | P2 | Welcome filtered-empty presentation | No-match filtered results are presented as an empty queue and offer first-record CTA | SOURCE-OBSERVED / REPRO-PENDING | Batch S: Welcome empty states |
| REG-FE-029 | P2 | Welcome primary load error | With zero rows/dataSource=error there is no error message or retry UI | SOURCE-OBSERVED / REPRO-PENDING | Batch S: Welcome error state |
| REG-FE-030 | P2 | Welcome query scope loss | Quick filter replaces all URL params and drops active date/department/doctor/search scope | SOURCE-OBSERVED / REPRO-PENDING | Batch T: URL filters |
| REG-FE-031 | P3 | Welcome orphaned selection | Selection checkboxes enabled with no bulk-action consumer | SOURCE-OBSERVED / REPRO-PENDING | Batch U: selection UX |
| REG-FE-032 | P3 | Welcome calendar date timezone | History date-only string parsed as UTC and displayed in browser local timezone | SOURCE-OBSERVED / REPRO-PENDING | Batch U: clinic date |
| REG-FE-033 | P3 | Default tabpanel label | All-departments tabpanel has no labelledby; corresponding control is not a real tab | SOURCE-OBSERVED / REPRO-PENDING | Batch U: accessibility |
| REG-FE-034 | P2 | Queue API response validation | Canonical queue response lacking queues is silently parsed as empty legacy response; null payload mapper also returns empty queues | SOURCE-OBSERVED / REPRO-PENDING | Batch V: API contract fail-closed |
| REG-FE-035 | P2 | Queue-manager async identity | Older doctor/date queue snapshot can overwrite more recent selection because hook has no request epoch guard | SOURCE-OBSERVED / REPRO-PENDING | Batch W: queue snapshot lifecycle |
| REG-FE-036 | P2 | Patient IDs treated as demos | Patient ID >=1000 is never hydrated from real patient API, regardless of backend identity | SOURCE-OBSERVED / REPRO-PENDING | X patient card identity |
| REG-FE-037 | P2 | Reference catalog request races | Older doctors/services/departments response may overwrite newer session-revalidation results | SOURCE-OBSERVED / REPRO-PENDING | Y reference-data freshness |
| REG-FE-038 | P2 | Patient deep-link identity | ?patientId selects all same-name records through q=FIO rather than filtering by the exact patient ID | SOURCE-OBSERVED / REPRO-PENDING | Z exact identity links |
| REG-FE-039 | P2 | Patient deep-link async freshness | A late lookup for patient A can overwrite q after navigation to patient B | SOURCE-OBSERVED / REPRO-PENDING | Z URL lifecycle |
| REG-FE-040 | P2 | Reschedule modal state leak | Date/time entered for one visit persist after closing and reopening modal for another visit | SOURCE-OBSERVED / REPRO-PENDING | AA reschedule lifecycle |
| REG-FE-041 | P2 | Grouped reschedule command | Aggregated row reschedule picks visit_ids[0] and then removes row identities as if all records moved | SOURCE-OBSERVED / REPRO-PENDING | AA aggregated reschedule |
| REG-FE-042 | P2 | Doctor queue absent vs empty | Queue manager synthesizes empty queue on no-match, bypassing not-found display and making missing scope appear empty | SOURCE-OBSERVED / REPRO-PENDING | AB queue read model |
| REG-FE-043 | P2 | Inline action permission SSOT | Registrar cancel/reschedule visibility is inferred solely from status rather than backend available_actions/can_* flags | SOURCE-OBSERVED / REPRO-PENDING | AC action authorization view |
| REG-FE-044 | P2 | Welcome revenue SSOT | Welcome revenue uses sum of appointment status/cost, not settled payment ledger, including partials/refunds | SOURCE-OBSERVED / REPRO-PENDING | AD truthful statistics |
| REG-FE-045 | P3 | Registrar CSV services/zero cost | CSV joins object services as [object Object], and hides legitimate zero cost by || fallback | SOURCE-OBSERVED / REPRO-PENDING | AE export semantics |
| REG-FE-046 | P3 | CSV formula whitespace gap | CSV formula neutralization only guards first-character =,+,-,@, not whitespace/control-prefixes | SOURCE-OBSERVED / REPRO-PENDING | AF spreadsheet export hardening |
| REG-FE-047 | P3 | Welcome analytics export | Statistics Export button does not export anything; callback only writes a log | SOURCE-OBSERVED / REPRO-PENDING | AG dead analytics control |
| REG-FE-048 | P3 | Registrar global shortcut semantics | Ctrl+2/3/4 do not prevent browser shortcuts and remain active when a select/contenteditable has focus | SOURCE-OBSERVED / REPRO-PENDING | AH keyboard coexistence |
| REG-FE-049 | P3 | Dialog focus timer | Delayed focus timeout is never cleared and can steal focus after quick close/reopen | SOURCE-OBSERVED / REPRO-PENDING | AI modal focus lifecycle |
| REG-FE-050 | P2 | Table numeric-only sort | Patient, appointment date, and status columns declare sortable but compare Number(text) -> NaN so they never order correctly | SOURCE-OBSERVED / REPRO-PENDING | AJ table sort contracts |
| REG-FE-051 | P2 | Table filtered page state | Search/filter/data shrink keeps currentPage; page 3 with 2 matches renders empty despite matching data and hides pagination | SOURCE-OBSERVED / REPRO-PENDING | AK table pagination reset |
| REG-FE-052 | P2 | Status presentation truthfulness | Canonical diagnostics/in_service/incomplete/rescheduled are displayed with scheduled badge because fallback invents scheduled | SOURCE-OBSERVED / REPRO-PENDING | AL canonical queue status display |
| REG-FE-053 | P3 | Search nested service DTOs | Search stringifies nested arrays of service objects as [object Object], excluding visible service names/codes from table search | SOURCE-OBSERVED / REPRO-PENDING | AM displayed-data search parity |
| REG-FE-054 | P3 | Context menu keyboard access | Context menu lacks menu role, initial focus and focus management; focus stays on underlying trigger while full-screen overlay is displayed | SOURCE-OBSERVED / REPRO-PENDING | AN table context menu accessibility |
| REG-FE-055 | P3 | DataTable row key stability | Row identity includes page-relative index; sorting/filtering/page transitions remount same record even when canonical IDs are unchanged | SOURCE-OBSERVED / REPRO-PENDING | AO table stable keys |

### REG-FE-001 — Row activation does not open details (P2 candidate)

**Code evidence:**

- [WorklistView.tsx L289–L301](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/views/WorklistView.tsx#L289-L301) passes an `onRowClick` callback that calls only `logger.info(...)`; comment indicates a details dialog could be opened, but no detail action is invoked.
- [EnhancedAppointmentsTable.tsx L211–L223](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/components/tables/EnhancedAppointmentsTable.tsx#L211-L223) forwards a supplied `onRowClick` to `DataTable`, making the callback part of the row-activation contract.
- [useRegistrarRowActions.ts](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/useRegistrarRowActions.ts) already supplies `openRecordPreview` and a working `view` action for explicit action controls.

**Potential impact:** a registrar clicks/keyboard-activates a row expecting to inspect the record, but nothing visible happens. Do not conflate this with the separate explicit `view` action, which may still work.

**Reproduction / fail-first test:** render `WorklistView` with one synthetic record; trigger the table row with a pointer and Enter/Space; assert an intentional details action occurs (or, if UX contract specifies non-actionable rows, assert row activation/focus affordance is absent). Check actual `DataTable` semantics and accessibility before selecting the remedy.

**Preferred remediation:** after verifying the intended UX, either wire row activation to `openRecordPreview` through an explicit prop/callback, or remove the misleading row-activation wiring. Preserve separate `view` and `edit` workflows, and verify keyboard activation and click-on-action-button behavior.

### REG-FE-002 — Search bypasses all-departments service normalization (P2 candidate)

**Code evidence:**

- [registrarWorklistRows.ts L275–L294](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/registrarWorklistRows.ts#L275-L294) returns `sortRegistrarRowsForPresentation(searched)` directly when `searchQuery` is present. The no-query path applies `filterServicesByDepartment(..., null, services)` to each row.
- [registrarServiceFilter.ts](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/registrarServiceFilter.ts) explicitly has a fallback from `queue_numbers[].service_name` when the aggregate `services` array is empty.

**Potential impact:** for an aggregated patient with no `services` array but queue numbers that can provide service codes, all-departments view may show services *before* entering a search term and omit them *after* searching. Only a **display** problem is alleged; there is no evidence of a backend queue/appointment mutation.

**Reproduction / fail-first test:** in `registrarWorklistRows.test.ts`, use synthetic data with a stable patient key, `queue_numbers` containing a service-name/code resolvable by `toServiceCode`, and `services: []`. Compare `computeRegistrarWorklistRows` with `searchQuery: ''` versus a query matching the patient; assert that the displayed services are equal. First establish that this data shape is supported by the current adapter/API.

**Preferred remediation:** apply the *same* presentation-only postprocessing to searched and unsearched aggregated rows, without changing queue identity, grouping, timing, ordering or server-owned routing. Regression test both search branches and multi-record aggregates.

### REG-FE-003 — Localized fallback not tracked by memo (P3 candidate)

**Code evidence:**

- [RegistrarPanel.tsx L259–L268](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/RegistrarPanel.tsx#L259-L268) passes `tI18n('registrarPanel.rp_unknown_patient')` into `computeRegistrarWorklistRows`, while the `useMemo` dependency array omits that resolved translated string and the translator/language.

**Potential impact:** when UI language changes without a concurrent change to the listed dependencies, a record lacking the patient display name may retain a fallback label in the previous language. Scope is limited to display text, not patient identity or data persistence.

**Reproduction / fail-first test:** render a registrar worklist with one **synthetic** record whose patient name is unavailable; change locale while keeping appointment/service/profile references stable; assert the fallback text updates. Do not add a test that passes solely because data reload changes an unrelated dependency.

**Preferred remediation:** compute `fallbackPatientLabel` as a render value and include that value in the memo dependency array; keep translated fallbacks separate from canonical patient data.


### REG-FE-004 — Quick filters disagree with backend queue/payment status semantics (P2 candidate)

**Code evidence:**

- [WelcomeView.tsx L392–L408](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/views/WelcomeView.tsx#L392-L408) writes `?status=queued` for "Активная очередь" and `?status=paid_pending` for "Ожидают оплаты".
- [registrarWorklistRows.ts L188–L192 and L239–L243](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/registrarWorklistRows.ts#L188-L243) compare that URL status strictly against `entry.status` on both detail and aggregate pathways; `payment_status` is not used for the payment filter.
- [Backend registrar _helpers.py L46–L50](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/backend/app/api/v1/endpoints/registrar_integration/_helpers.py#L46-L50) preserves the server queue status `waiting` (and defaults absent/paid status to `waiting`); [registrarQueueAdapter.ts L46–L48 and L87–L94](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/registrarQueueAdapter.ts#L46-L94) stores canonical queue status separately from `payment_status`.

**Potential impact:** an active `waiting` patient may be absent from the "active queue" view, and a patient whose **payment_status** is pending may be absent from "awaiting payment" if their queue status is `waiting`. Status aliases/permissions may change exact affected sets; validate against real canonical DTOs before deciding which statuses represent "active".

**Fail-first test:** with synthetic backend records `{status:'waiting',payment_status:'pending'}`, exercise both Welcome filters and `computeRegistrarWorklistRows`; assert active-queue and unpaid filters follow the chosen backend-owned semantics. Cover both department and aggregate tabs, and confirm no status mutation is introduced.

**Fix direction:** separate UI filter concepts `queueStatus` and `paymentStatus` or interpret legacy URLs through a single canonical backend-aligned predicate. Keep backend queue and payment truth distinct, preserve existing shared URLs or migrate them intentionally.

### REG-FE-005 — Worklist date may diverge from `?date` (P2 candidate)

**Code evidence:**

- [useRegistrarWorklistData.ts L243–L250](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L243-L250) chooses the API date from `searchParams.get('date')` when calendar mode is not active.
- [useRegistrarWorklistData.ts L401–L477](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L401-L477) loads once at mount and reloads on calendar state/date changes, but no dedicated `?date` dependency effect when `showCalendar === false`. Changing search params rebuilds `loadAppointments` but the guarded initial effect does not load again.
- [WorklistView.tsx L145–L154](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/views/WorklistView.tsx#L145-L154) always labels the worklist "today" when calendar is closed, even if the initial API request used a historical `?date`. [QueueView.tsx L82–L99](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/views/QueueView.tsx#L82-L99) can change the URL date.

**Potential impact:** direct navigation to `/registrar?date=YYYY-MM-DD` can show historical rows under a "today" label. Editing `?date` through same-mounted navigation can retain data from the earlier date until another refresh. This is a **presentation/data-loading mismatch**, not proof that the server stores records under the wrong date.

**Fail-first test:** mount the hook with a non-today URL date, assert request `target_date` and visible date heading; rerender with another URL date while `showCalendar=false`, assert a new request and correct rows. Test back/forward and concurrent responses.

**Fix direction:** derive one effective worklist date and make the data-loading effect depend on it, not every incidental filter or appointment-count change; reuse the request sequence guard; render that effective date consistently in the header.

### REG-FE-006 — Welcome table bypasses action confirmation (P2 candidate)

**Code evidence:**

- [WelcomeView.tsx L641–L659](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/views/WelcomeView.tsx#L641-L659) routes `in_cabinet` and `complete` directly to `updateAppointmentStatus` without a confirmation.
- [useRegistrarRowActions.ts L89–L129](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/useRegistrarRowActions.ts#L89-L129) awaits a shared confirmation before the same actions on the main table, and [useRegistrarRowActions.test.ts](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/__tests__/useRegistrarRowActions.test.ts#L1-L15) documents that contract.

**Potential impact:** where the backend exposes these actions to the current role, a misclick in the Welcome table can send a state-changing command without the confirmation protection used elsewhere.

**Fail-first test:** render the Welcome table with synthetic record/action permissions and trigger `in_cabinet`/`complete`; verify no network command occurs unless the user confirms. Also verify keyboard activation and explicit action buttons do not double-submit.

**Fix direction:** route Welcome commands through the *same* `useRegistrarRowActions` handler or one centralized confirmation-aware action service. Preserve backend RBAC and available-actions checks.

### REG-FE-007 — HTTP 429 fails to produce an explicit refresh-failure state (P2 candidate)

**Code evidence:**

- [useRegistrarWorklistData.ts L347–L357](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L347-L357) sets 60-second cooldown and returns on 429 without `LOAD_FAILED` or a rate-limit-specific state.
- [useRegistrarWorklistData.test.ts L204–L212](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/__tests__/useRegistrarWorklistData.test.ts#L204-L212) explicitly pins the existing `dataSource='loading'`, `appointmentsLoading=false` outcome for a non-silent 429. This is **known preserved behavior**, not an unanticipated code typo.

**Potential impact:** on primary load, the worklist may leave the spinner but not show the intended error/retry state; on refresh, kept data may not be visibly marked stale despite the failed attempt. A user could mistake the state for a healthy/empty result.

**Fail-first test:** mock a 429 on initial load and after a successful load, assert explicit rate-limited/retry feedback and preserved rows; confirm auto-refresh respects the cooldown. Update the legacy test only when intentionally replacing the pinned behavior.

**Fix direction:** model rate limiting as an explicit state, preserving previous rows with stale indication, exposing the cooldown/retry action, and avoiding a false success claim. No backend throttling change in this audit.

### REG-FE-008 — Manual refresh announces success before the outcome (P2 candidate)

**Code evidence:** [WelcomeView.tsx L418–L423](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/views/WelcomeView.tsx#L418-L423) calls `loadAppointments(...)` without awaiting it and immediately calls `notify.success(t('misc.data_updated'))`. The data hook catches network errors internally, so a `Promise<void>` resolution alone is not currently proof of successful refresh.

**Potential impact:** the registrar can see "data updated" despite a failed API request/429, while the table still displays old or no data.

**Fail-first test:** stub a pending/rejected/429 fetch, click Refresh, assert no success toast before a verified successful response; assert an appropriate failure or rate-limit indication. Test a successful refresh separately.

**Fix direction:** expose a reliable fetch-result outcome from the hook (rather than assuming any awaited void return means success), then show success only for a current, successful request. Preserve last-known data on failure.

### REG-FE-009 — Reschedule optimistic removal mixes ID namespaces (P2 candidate)

**Code evidence:**

- [useRegistrarReschedule.ts L33–L80](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/useRegistrarReschedule.ts#L33-L80) unions raw `id`, `visit_id`, `queue_entry_id`, `appointment_id` and aggregate IDs as **untyped strings**, then removes any row with *any* matching ID.
- [RescheduleSlots.tsx L99–L107](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/views/RescheduleSlots.tsx#L99-L107) invokes the optimistic removal after the reschedule succeeds, before queue reload.

**Potential impact:** IDs from different tables may overlap. Example (synthetic): rescheduling row A `{id:10,visit_id:20}` puts `20` in the removal set; unrelated row B `{id:20,visit_id:21}` is hidden because `B.id=20`, even though B is a different entity. The normal refresh may restore B; a failed refresh could prolong a misleading worklist state. Backend reschedule identity is unaffected by this specific client-side filter.

**Fail-first test:** use two synthetic records with overlapping cross-table IDs and different canonical record refs; call `removeRescheduledAppointmentFromView` for A; assert only the intended row disappears. Add multiple-record aggregate and failed-refresh cases.

**Fix direction:** compare type-scoped canonical record references, not bare cross-entity IDs. If a safe identity is not available, do not remove optimistically; let an authoritative reload determine the list.


### REG-FE-010 — Existing patient profile edits may not persist in create mode (P2 candidate)

**Code evidence:** [AppointmentWizardV2.tsx L850–L872](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L850-L872) stores the selected patient's `id` and editable form data; [PatientStepV2.tsx L290–L323](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/PatientStepV2.tsx#L290-L323) exposes birth date and address editing. On submit, [AppointmentWizardV2.tsx L2069–L2115](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2069-L2115) calls `createPatient` only when `!editMode && !patientId`. With `editMode === false` and the explicitly selected patient's non-null ID, that branch is skipped. The subsequent cart creation carries `patient_id` and service/quote fields but no patient profile changes ([L2690–L2702](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2690-L2702)).

**Potential impact:** registrar chooses an existing patient, corrects address or birth date in the creation form, and successfully creates an appointment; the displayed correction is not saved to the patient card. This is contingent on those fields being intended as editable patient-profile data in create mode (product contract to verify).

**Fail-first test:** select an existing synthetic patient and change their address/birth date, submit a new appointment. Assert the resulting patient record reflects the intended changes or that the UI explicitly prevents/makes clear that profile edits will not be saved. Confirm the cart is linked to the existing patient ID and never silently creates a second patient.

**Remediation direction:** choose and document the workflow contract: update the existing profile through an explicit, independently verified patient-card save, or make profile fields read-only in booking mode with a deliberate "Edit patient" action. Avoid implicit phone/FIO reassociation.

### REG-FE-011 — Separate patient mutation before queue edit can yield a partial save (P2 candidate)

**Code evidence:** [AppointmentWizardV2.tsx L2180–L2196](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2180-L2196) calls `await updatePatient(patientId, { sex: ... })` before entering the queue/full-update/edit-delta paths. The later [edit-delta API call L2425–L2467](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2425-L2467) is an independent mutation that may reject (including quote/concurrent-update 409). A QR lookup path also updates an attached patient before the edit is committed ([L1992–L2025](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L1992-L2025)).

**Potential impact:** when editing a queued visit, the patient sex/birth date/address can persist, followed by a rejected edit-delta/queue operation. The wizard reports an unsuccessful appointment edit while the patient record has already changed. This is a **partial cross-domain operation**, not evidence of wrong patient identity or a failed backend transaction.

**Fail-first test:** with synthetic patient and queue entities, mock `updatePatient` success followed by `applyRegistrarEditDelta` rejection (409) or QR full-update failure. Assert the user receives truthful **partial-save** feedback, the patient card outcome is known, and retry cannot silently duplicate commands. Check the canonical backend ownership/transaction model before designing any atomicity change.

**Remediation direction:** avoid a pre-save outside the authoritative edit operation when possible. Prefer backend transaction-aware command ownership if the domain allows it; otherwise explicitly surface the successful patient write and failed queue command, and prescribe safe reconciliation. Any modification requires the repository mandatory gate due to patient/clinical/queue boundaries.

### REG-FE-012 — Stale service catalogue can overwrite active wizard data (P2 candidate)

**Code evidence:** [AppointmentWizardV2.tsx L914–L951](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L914-L951) fetches a date-specific service catalogue, then unconditionally calls `setServicesData` / `setFilteredServices` on resolution, with no generation guard or abort. [L1045–L1060](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L1045-L1060) invokes the loader when `isOpen` or the loader identity/date changes. [L1009–L1039](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L1009-L1039) uses the resulting `servicesData` to resolve currently displayed cart references.

**Potential impact:** open wizard for date A, start catalogue fetch; then open/edit record for date B while request A remains pending. If B resolves first and A later, A's catalogue can replace B's and hydrate the B cart against obsolete doctor/service metadata. Backend validation still owns queue assignment and may reject; this finding concerns misleading frontend choices/quote and potential wrong user decision, not proven unauthorized assignment.

**Fail-first test:** with deferred promises, return date B before date A, assert that current selected date B catalogue stays visible and cart references/eligibility are not overwritten by A. Also test closing/reopening the wizard and a request failure after a successful catalogue load.

**Remediation direction:** use an abort signal or monotonic request-ID/active-date guard; reset or explicitly mark catalogue stale during a date/record change. Verify quote and doctor-selection data update coherently.

### REG-FE-013 — Development logging leaks patient-identifying strings (P2 privacy candidate)

**Code evidence:** [AppointmentWizardV2.tsx L2034–L2046](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2034-L2046) constructs a `logger.warn(`...${wizardData.patient.phone}...`)` message with the raw phone in a **primitive string**. [L1931–L1940](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L1931-L1940) passes `{ fio, phone, birth_date }` as a log object. [logger.ts L15–L41](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/utils/logger.ts#L15-L41) does not list the bare field name `fio`, and [L146–L171](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/utils/logger.ts#L146-L171) passes primitive strings through without sanitization. Logger `warn` and `log` output only in development by default, so **no production log emission from these specific logger methods has been shown**.

**Potential impact:** real patients' phone or name can appear in developer console during edit-mode QR patient resolution in development/test builds. This violates the repository privacy discipline even if production builds normally suppress these logger methods.

**Fail-first test:** in a synthetic-only logger test, pass a fabricated phone in an interpolated string and `{ fio: 'SYNTHETIC Patient' }`; assert outputs are redacted (or replace these call sites with non-PII diagnostic facts) without weakening error observability. Verify production/dev behavior separately.

**Remediation direction:** remove patient values from diagnostic message strings; log only safe flags/record-kind/error-code. Harden logging conventions so primitive PHI cannot bypass scrubber. Keep this entirely separate from patient/queue behavior changes.

### Wizard follow-up investigation (not yet a numbered finding)

There remains an older [batch endpoint + fallback branch in AppointmentWizardV2.tsx L2495–L2590](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2495-L2590): after a batch error it can continue toward cart creation. The earlier `editDeltaBuild.items.length > 0` return and the QR full-update short-circuit appear to guard most real edit scenarios; **reachability and duplicate-write impact are not proven**. Do not label P1 or change the branch without a fail-first route-selection test and backend reconciliation evidence. The main `createRegistrarCart` path already uses a submission lock and payload-bound idempotency key.


### REG-FE-014 — Context-menu status actions claim success on rejected command (P2 candidate)

**Code evidence:** [useRegistrarRowActions.ts L184–L196](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarRowActions.ts#L184-L196) and [L199–L214](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarRowActions.ts#L199-L214) `await updateAppointmentStatus(...)` and **unconditionally** emit `notify.success` for "in_cabinet" and "complete". [useRegistrarActions.ts L100–L126](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarActions.ts#L100-L126) catches HTTP/contract errors or rejects unsupported actions and resolves **`null`**, rather than rejecting. The latter also emits its own success toast on success, so a successful context action may produce **two** success notifications. [Existing row-actions test L105–L111](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/__tests__/useRegistrarRowActions.test.ts#L105-L111) mocks a void/undefined return and only asserts command invocation.

**Potential impact:** an unsuccessful attempt to send a patient to a room or complete a visit is followed by a contradictory success toast; a genuine success may be toasted twice. Affected surface is the **context menu**, distinct from the earlier Welcome confirmation issue REG-FE-006.

**Fail-first test:** render the row-action hook with `updateAppointmentStatus` returning `null` (for declined backend action, permission failure or network error), confirm the menu action, and assert **zero** success toasts. With an actual successful result, assert one coherent success toast from a single owner, not two. Include both `in_cabinet` and `complete`.

**Remediation direction:** gate the context-menu acknowledgement on an explicit successful command result, ideally centralize success/error notifications in `useRegistrarActions`; preserve confirmation, auth/RBAC and backend-owned available-actions semantics.

### REG-FE-015 — Partial batch status command leaves worklist unsynchronized (P2 candidate)

**Code evidence:** [backend registrar_wizard/_visits.py L1471–L1493](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_wizard/_visits.py#L1471-L1493) executes one command per record and returns `success=false` whenever **any** item failed, with `success_count`, `failed_count` and per-record results. Backend actions are not one all-or-nothing batch transaction; for instance, the cancel-visit record branch explicitly commits within the per-item operation ([L951–L981](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_wizard/_visits.py#L951-L981)); an existing characterization test demonstrates the `success_count=1, failed_count=1` shape ([test_registrar_queue_cancel_r13.py L309–L357](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/tests/characterization/test_registrar_queue_cancel_r13.py#L309-L357)). [useRegistrarActions.ts L67–L81 and L109–L126](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarActions.ts#L67-L126) treats a response with `success=false` as a thrown error, and only refreshes the worklist in the all-success path. Its catch reports an error and returns `null`; neither handler reconciles successful records in a partial outcome.

**Potential impact:** for an aggregated/multi-record action that succeeds on A and fails on B (e.g. concurrent status change or unavailable action), UI can continue displaying A as actionable in the old state, without explaining what succeeded. Repeating the command against stale rows can cause user confusion or an unnecessary second state transition attempt. This is *not* evidence of silent corruption: the server owns validation and may reject the duplicate.

**Fail-first test:** feed `handleStartVisit` and `updateAppointmentStatus` a synthetic response `{success:false,success_count:1,failed_count:1,results:[{success:true,record_id:1},{success:false,record_id:2,error:'conflict'}]}`; assert one authoritative refresh/reconciliation happens even though overall action failed; assert user sees **partial success with failed record details** and cannot misread it as zero committed effects. Test all-failed and all-success outcomes separately, and backend permissions independently.

**Remediation direction:** return typed structured outcomes rather than `null`-only errors for partial batches, refresh after any committed item and present precise partial-result feedback. Do not automatically retry the entire group; first reconcile fresh server state and target only records still actionable. Any implementation crossing visit/queue contracts requires mandatory gate.

### REG-FE-016 — Cart banner counts doctors, not prospective visits (P3 candidate)

**Code evidence:** [CartStepV2.tsx L589–L616](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/CartStepV2.tsx#L589-L616) builds `doctorGroups` keyed by `item.doctor_id || 'no_doctor'`, then labels its size as `Будет создано визитов`. In contrast, the actual payload grouping function [wizardUtils.ts L1084–L1154](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/wizardUtils.ts#L1084-L1154) keys each grouped visit by either **resource queue tag** or **doctor ID**, *plus visit date/time*. Different resource tags with no physician are two groups for save but one `no_doctor` card group in the banner calculation; because this component returns `null` when `groupCount <= 1`, the informative visit-count banner is **absent** in this two-visit scenario. A mixed doctor/resource cart can also undercount when the banner appears. Conversely, the same doctor with different visit times may form two grouped visits while banner still counts one.

**Potential impact:** the registrar sees an inaccurate prospective visit count just before confirming a multi-resource or multi-time booking. This is a presentation forecast issue; it does not assert incorrect backend queue allocation.

**Fail-first test:** for synthetic cart with two doctorless services on different resource tags and same date, assert the banner equals `groupCartItemsByVisit(...).length` (two), and for two same-doctor items with distinct visit times verify both counts. Cover grouped same-doctor same-time case (one). Only claim the payload forecast, not actual persisted visit count until backend reconciliation.

**Remediation direction:** derive prospective count from the same pure grouping used to prepare the request or rename banner to a truthful count of distinct doctors/resource groups. Do not introduce a second client-side queue owner or override backend SSOT.

### Verified guardrails and unconfirmed routing hypothesis

- **Read and write doctor assignment:** [CartStepV2.tsx L310–L331](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/CartStepV2.tsx#L310-L331) uses `filterDoctorsForService`, [wizardUtils.ts L183–L209](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/wizardUtils.ts#L183-L209) honors the pinned `service.doctor_id`, and [backend registrar_doctor_eligibility.py L278–L355](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/services/registrar_doctor_eligibility.py#L278-L355) rejects invalid pinned-doctor/resource routing in write commands. No claim of a missing doctor-owner check is made on the inspected path.
- **Edit delta:** [AppointmentWizardV2.tsx L2394–L2484](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2394-L2484) routes a non-empty edit-delta to `applyRegistrarEditDelta` and returns on success/failure; QR full-update has its own return guard. The old batch→cart fallback at [L2494–L2588](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2494-L2588) is still present but **reachability is unproved** for the current canonical edit pathway; do not promote it to a duplicate-booking P1 without a concrete reproduction.
- **No source edits, no tests:** backend and frontend were inspected read-only. The exact effects of these candidates remain subject to focused regression tests.


### REG-FE-017 — CancelDialog reports success on no-op or partial cancel (P2 candidate)

**Code evidence:** [RegistrarDialogsLayer.tsx L144–L168](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/RegistrarDialogsLayer.tsx#L144-L168) forwards an `onCancel` callback to `CancelDialog`. Its `if (!result) return;` branch resolves the callback normally when `runRegistrarRecordAction` produces `null` after missing record references or action unavailability ([useRegistrarActions.ts L44–L64](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarActions.ts#L44-L64)). For a partial server batch `{success:false,success_count>0,failed_count>0}`, the same callback displays `notify.warning`, refreshes, and resolves. [CancelDialog.tsx L58–L83](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/dialogs/CancelDialog.tsx#L58-L83) treats **every normally resolved** `onCancel` as complete success, displays `toast.success` and calls `onClose()`.

**Potential impact:** a registrar may receive a "record successfully canceled" toast although no record was canceled; partial cancellation may produce a contradictory warning followed by a blanket success toast and automatic close. The user may incorrectly trust the cancellation of outstanding entries. This adds a **dialog-level acknowledgement defect** distinct from REG-FE-015 (stale worklist after partial status changes).

**Fail-first test:** mount `CancelDialog` with real-like `RegistrarDialogsLayer` callback and synthetic records. For `runRegistrarRecordAction→null`, assert *no success toast*, no close, and an explicit error; for `{success:false,success_count:1,failed_count:1}`, assert partial feedback with failed record detail and no blanket complete-success; for all-success, assert exactly one success and close. Cover backend action unavailability and mixed aggregate record refs.

**Fix direction:** define typed outcomes (`all_success`, `partial_success`, `no_op`, `failed`) across the dialog/command boundary. Require explicit positive result before success/close; partial outcomes should be reconciled with backend and identified to the registrar. Avoid interpreting "resolved promise" as proof of committed cancellation.

### REG-FE-018 — Post-wizard retry is bypassed by swallowed fetch failures (P2 candidate)

**Code evidence:** [useRegistrarWizard.ts L154–L168](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWizard.ts#L154-L168) calls `Promise.all([loadAppointmentsRef.current({silent:true}),loadIntegratedData()])` and retries the worklist once only if the promise **rejects**. However [useRegistrarWorklistData.ts L347–L395](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L347-L395) handles HTTP 429 and network/API errors internally, dispatching failure state or returning and **not throwing**. [useRegistrarData.ts L54–L92 and L138–L165](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarData.ts#L54-L165) uses `Promise.allSettled` and catches failed reference-data fetches internally, so the outer `Promise.all` generally resolves even on incomplete data. Non-silent `loadIntegratedData` also clears doctors/services/departments before fetching ([L57–L70](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarData.ts#L57-L70)).

**Potential impact:** after successful creation/edit, the wizard closes and presents a payment/print handoff, but a failed refresh may leave stale worklist rows (or empty reference lists) without executing the documented retry. This is **not** evidence that the successful backend save rolled back; it is a screen-reconciliation contract failure. A later periodic/foreground refresh may eventually repair it.

**Fail-first test:** mock a successfully saved wizard result, make the worklist request respond with 429 or reject, and independently fail one of the reference-data requests. Assert a distinguishable refresh outcome reaches the coordinator, a bounded retry/reconciliation policy actually runs when appropriate, and the user sees a stale-data indication rather than an incorrect claim of refreshed data. Keep committed save success separate from refresh failure. Verify that a 429 cooldown is respected rather than blindly hammering it.

**Fix direction:** return an explicit `LoadOutcome`/failure enum from the fetch hooks (including partial metadata failure) and evaluate it in `handleWizardComplete`; retry only retryable failures and give truthful stale-state feedback. Do not throw from already committed command paths in a way that encourages users to resubmit a booking.

### REG-FE-019 — Duplicate success toasts after wizard save (P3 candidate)

**Code evidence:** [AppointmentWizardV2.tsx L2827–L2835](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2827-L2835) calls `toast.success` immediately before `onComplete?.(result)` in the cart-save path; other successful branches have the same pattern ([L2461–L2468](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2461-L2468)). Parent [useRegistrarWizard.ts L122–L144](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWizard.ts#L122-L144) invokes `notify.success` again on the completion callback. [notify.ts L1–L22](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/services/notify.ts#L1-L22) delegates `notify.success` to the *same* `react-toastify.toast.success`.

**Potential impact:** one successful registration/edit may create two success notifications for the same mutation, increasing noise and reducing clarity when payment/print opens. This is cosmetic/feedback ownership, not a duplicate backend write.

**Fail-first test:** render the wizard and parent callback in a synthetic saved-result path and assert exactly one successful save notification and the intended next dialog; repeat for edit-delta and create-cart.

**Fix direction:** choose one owner for the success toast (typically the orchestration layer) and eliminate duplicate acknowledgement without changing save completion, payment handoff or error semantics.

### Focused review pass: Group 1 — patient registration orchestration (2026-10-30)

**Primary files source-read at `main` SHA `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`:**

- [RegistrarPanel.tsx](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/RegistrarPanel.tsx#L1-L498) — routing, callback composition, open/close entrypoints, worklist and dialog wiring.
- [useRegistrarWizard.ts](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWizard.ts#L1-L196) — reducer transitions, open/edit/create state, post-save refresh and payment/print handoff.
- [RegistrarDialogsLayer.tsx](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/RegistrarDialogsLayer.tsx#L1-L315) — cancellation/payment/wizard dialog callbacks and local ErrorBoundary.

**Cross-checked:** `CancelDialog.tsx`, `useRegistrarActions.ts`, `useRegistrarWorklistData.ts`, `useRegistrarData.ts`, `AppointmentWizardV2.tsx`, `ErrorBoundary.tsx`, `useRegistrarNavigation.ts`, `useRegistrarHotkeys.ts`, `notify.ts`, `useRegistrarDialogs.test.ts` and source contract tests.

**Not re-filed as a new bug:** the wizard reducer deliberately preserves edit state on `SET_OPEN`; direct normal wizard `onClose` in `RegistrarDialogsLayer` resets mode and initialData, and the Ctrl+N/new-appointment explicit path resets them as well. `onEmptyStateCta` opens with `SET_OPEN` only, so a stale-edit concern **needs a realistic preceding close-without-reset reproduction**, not just a theoretical reducer state. Similarly, the local ErrorBoundary does implement an explicit retry handler. No P0/P1 was established in this source-only group.


### REG-FE-020 — Superseded request clears in-flight guard of newer load (P2 candidate)

**Code evidence:** [useRegistrarWorklistData.ts L199–L225](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L199-L225) allows non-auto/manual/date loads to overlap, shares `loadAppointmentsInFlightRef`, and assigns a monotonically increasing `requestId`. [L386–L392](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L386-L392) **always** executes `loadAppointmentsInFlightRef.current = false` in `finally`, even if `isSuperseded()` is true and a newer request is still running. The comment about superseded cleanup applies only to the `LOAD_FINALLY` dispatch, not to this ref. Auto-refresh consults the ref in [L491–L506](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L491-L506). A superseded 429 also updates the shared cooldown without an `isSuperseded()` check ([L348–L356](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L348-L356)).

**Potential impact:** A (slow) → B (newer, still pending) → A settles → shared in-flight flag becomes false while B is pending. On the next auto-refresh tick C can start and claim a newer sequence ID; B's correct response is then discarded as superseded even though C was an unnecessary refresh. If A returns 429, stale A can also suspend auto-refresh for 60 seconds after B has otherwise succeeded. This is **not** evidence that server-side queue priority or numbers change; it is a frontend data freshness/race concern.

**Existing test gap:** [useRegistrarWorklistData.test.ts L290–L368](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/__tests__/useRegistrarWorklistData.test.ts#L290-L368) covers late A settling *after* B, but does not cover A settling **while B remains pending and timer C fires**.

**Fail-first test:** with fake timers/deferred promises start A, B; settle A while B is still in flight; advance 30-second interval and assert *no C request*; resolve B and assert B wins, loading guard releases; also test stale A returning 429 does not start a fresh cooldown that blocks successful B's later refresh. Test silent and non-silent combinations.

**Fix direction:** associate in-flight state and cooldown effects with the currently authoritative request, or use a separate active-request counter and explicit source-aware refresh scheduling. Keep request-sequence/latest-wins behavior; avoid treating all overlapping requests as one Boolean.

### REG-FE-021 — Auto-refresh sees stale snapshots of other dialog states (P2 candidate)

**Code evidence:** [RegistrarPanel.tsx L177–L187](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/RegistrarPanel.tsx#L177-L187) writes the current payment/cancel/print/preview/context/reschedule flags to `anyDialogOpenRef.current` during render. [useRegistrarWorklistData.ts L474–L510](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L474-L510) reads `Boolean(anyDialogOpenRef.current)` **once while creating** its interval. Only `showWizard`, `loadAppointments`, and the stable ref identity are in the effect dependency list; the callback at L491–L506 never rechecks the ref. The code comments explicitly note preserving stale-closure behavior. [useRegistrarWorklistData.test.ts L270–L281](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/__tests__/useRegistrarWorklistData.test.ts#L270-L281) uses a ref with static `current:false`; there is no open/close interval test.

**Potential impact:** if the timer was created with all dialogs closed, opening a payment/cancel/preview dialog alone leaves it running, allowing background queue changes under the modal. Conversely, if the effect initialized when one of these dialogs was open (and returned early), closing it without changing `showWizard` or another dependency may leave periodic refresh **disabled** until an unrelated re-render re-creates the effect. WebSocket-triggered loads are not covered by this pause policy and need separate product decision.

**Fail-first test:** with fake timers, keep `showWizard=false` and stable callback identities. Begin with `anyDialogOpenRef.current=false`, then toggle a payment dialog to true and advance interval: assert the intended pause. Begin with true, close it, advance 30 seconds: assert refresh resumes. Ensure Ctrl+N wizard-open behavior remains intact and tests use synthetic records only.

**Fix direction:** observe other dialog state in the effect dependency model, or check the *latest* `anyDialogOpenRef.current` on each interval tick while maintaining a scheduled timer. Decide the intended real-time behavior explicitly: a previous P-026 note discusses the tradeoff of keeping a background list up to date, whereas R-26 calls for pausing when a modal is open. Preserve actual product contract after the decision, not an accidental ref snapshot.

### REG-FE-022 — Synthetic queue-number presence can create a false active-queue badge (P2 candidate)

**Code evidence:** The backend [registrar_integration/_queue_ops.py L1401–L1460](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_integration/_queue_ops.py#L1401-L1460) initializes `queue_entry_number=idx` and only replaces it when a real queue entry is found; `idx` is a presentation ordinal, not necessarily an allocated queue number. Its owner resolver [L352–L432](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_integration/_queue_ops.py#L352-L432) independently returns `daily_queue_id=None` for a visit or appointment without a proved linked queue. The read model serializes both fields ([registrar_integration/_today_queues.py L588–L600 and L663–L699](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_integration/_today_queues.py#L588-L699)). In the frontend, [registrarQueueAdapter.ts L36–L38 and L104–L122](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarQueueAdapter.ts#L36-L122) unconditionally turns the server `number` (including fallback ordinal) into a one-element `queue_numbers` array. Both [computeDoctorStats / computeDepartmentStats L53–L114](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarWorklistRows.ts#L53-L114) infer `hasActiveQueue` from nonempty `queue_numbers` and a waiting/called/in_service status, without checking a real `daily_queue_id`; [Tabs.tsx L282–L311](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/navigation/Tabs.tsx#L282-L311) presents this as an **active queue** indicator.

**Potential impact:** a confirmed/waiting appointment or visit that has no actual DailyQueue link can show an apparent queue number (even ordinal zero) and trigger the "Активная очередь" status badge. This conflates *scheduled patient* with *allocated queue entry*. Because the ordinal originates in the backend read-model fallback, the robust repair likely requires an explicit canonical `queue_number_assigned`/nullable allocated-number fact, **not** guessing ownership or number assignment in React.

**Fail-first test:** construct a backend-integrated queue read response for a synthetic visit/appointment without a matching queue entry (`daily_queue_id:null`, `status:'waiting'`, `number:0` or the ordinal). Pass it through `adaptQueueEntry` and stats; assert it does not produce an active-queue indicator or a falsely allocated queue number. Also verify the positive path with `daily_queue_id` and valid allocated number and preserve per-entry `queue_owner_kind/id`. Backend integration/contract test should demonstrate the linked and unlinked cases before changing DTOs.

**Fix direction:** canonical backend should distinguish display-order ordinal from allocated queue number and supply the truth to the adapter. This touches queue SSOT/read-model semantics; run the mandatory repository gate before any source change. This candidate is not a claim that wrong numbers were actually allocated.

### Group 2 focused review — queues (2026-10-30)

**Named source files inspected at `main` SHA `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`:** [useRegistrarWorklistData.ts](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L1-L547), [registrarWorklistRows.ts](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarWorklistRows.ts#L1-L477), [registrarQueueAdapter.ts](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarQueueAdapter.ts#L1-L142).

**Necessary cross-checks:** `frontend/src/utils/registrarAggregation.ts`, `frontend/src/utils/dateUtils.ts`, `frontend/src/components/navigation/Tabs.tsx`, `frontend/src/pages/registrar/useRegistrarDoctorWorklistFacts.ts`, `frontend/src/pages/RegistrarPanel.tsx`, three focused test files `__tests__/useRegistrarWorklistData.test.ts`, `__tests__/registrarWorklistRows.test.ts`, `__tests__/registrarQueueAdapter.test.ts`, backend `registrar_integration/_today_queues.py` and `_queue_ops.py`, plus ADR-001. All were read-only; **no tests were executed**.

**Verified positive protections:**

- Worklist flattening maps one backend entry to one row, with no client dedup; per-row `queue_owner_kind/id` and real `daily_queue_id` are passed through instead of deriving owner from a specialty bucket ([adapter L53–L73](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarQueueAdapter.ts#L53-L73)).
- Newer-request ID guard checks after both queue fetch and asynchronous patient enrichment ([worklistData L223–L253; L321–L336](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L223-L336)); existing tests cover late superseded success/failure. This is effective for *row content* even though REG-FE-020 highlights a separate in-flight flag/cooldown issue.
- Client today-date formatter explicitly uses `Asia/Tashkent` ([dateUtils.ts L168–L180](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/utils/dateUtils.ts#L168-L180)), matching backend `timezone`; **no browser-local-timezone defect is claimed**.
- Status and doctor tabs use backend-provided `queue_owner_kind/id` ([registrarWorklistRows.ts L48–L67](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarWorklistRows.ts#L48-L67)). Existing tests cover resource vs doctor identity, scope counters and no-match states.
- REG-FE-002 (all-departments search skips service formatting), REG-FE-005 (URL date reload) and REG-FE-007 (429 state) remain already indexed, **not duplicated**. `computeDepartmentStats.hasActiveQueue` intentionally scans even other-date rows in a pinned unit test ([registrarWorklistRows.test.ts L103–L113](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/__tests__/registrarWorklistRows.test.ts#L103-L113)); treat any policy change there as a separate product/contract decision, not an automatically accepted bug.

**Unnumbered follow-up:** the `queueUpdated` event listener schedules a 300/500 ms `setTimeout` ([useRegistrarWorklistData.ts L421–L453](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L421-L453)) without clearing already scheduled callbacks during cleanup. A post-unmount request is plausible; assign a new finding only after a deterministic unmount/fake-timer test demonstrates material impact. An event is also stamped as recent *before* refresh succeeds, which may delay retry on failed refresh, but overlaps REG-FE-007/020 and needs reproduction.


### REG-FE-023 — Schedule-next action visible but not handled by registrar action router (P2 candidate)

**Code evidence:** [AppointmentContextMenu.tsx L186–L201](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/tables/AppointmentContextMenu.tsx#L186-L201) renders `schedule_next` for every non-doctor view, and [L231–L235](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/tables/AppointmentContextMenu.tsx#L231-L235) invokes `onAction('schedule_next',row)` and closes the menu. The entire [useRegistrarRowActions.ts L170–L258](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarRowActions.ts#L170-L258) switch has no `schedule_next` case (the table switch at [L86–L168](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarRowActions.ts#L86-L168) lacks it as well). Contrast: the separate cardiologist surface handles `schedule_next` explicitly in [CardiologistPanelUnified.tsx L1142–L1145](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/CardiologistPanelUnified.tsx#L1142-L1145). Backend does **not** authorize this action generally for registrars: [_helpers.py L162–L175, L209–L215](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_integration/_helpers.py#L162-L215) offers it only when clinical state, patient identity and permitted physician role match. Context menu does not consult `available_actions`/ `can_schedule_next` for this item.

**Potential impact:** registrar clicks a plausible "Назначить следующий визит" menu item; menu closes with **no workflow** or explanation. If implementers simply wire the doctor action without respecting backend entitlement, it could also violate role boundaries. The defect is in the action's visibility/routing, not proof of a backend authorization bypass.

**Fail-first test:** mount `AppointmentContextMenu` on a synthetic registrar row lacking `schedule_next` authorization and assert the option is absent/disabled with an explained reason; for a role-authorized row where a supported flow exists, assert exactly one typed action routes to the appropriate UI. Assert the registrar action router never silently accepts an advertised unhandled action.

**Fix direction:** remove or entitlement-gate this control from registrar menu until a real, authorized registrar scheduling flow exists. Do not copy a cardiologist-only handler into registrar without explicit domain/RBAC approval and mandatory project gate.

### REG-FE-024 — Aggregated patient rows hide backend-authorized non-payment context actions (P2 candidate)

**Code evidence:** [registrarAggregation.ts L267–L333 and L434–L447](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/utils/registrarAggregation.ts#L267-L447) creates all-departments aggregate rows, storing each record's `available_actions` and `can_*` flags inside `grouped_records` but **not on the aggregate root**. Finalization at [L522–L589](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/utils/registrarAggregation.ts#L522-L589) preserves that shape. [AppointmentContextMenu.tsx L30–L49](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/tables/AppointmentContextMenu.tsx#L30-L49) checks only the root `can_*` flags/`available_actions` for non-payment actions; its `payment` branch deliberately delegates to `getBackendActionAvailability` which supports grouped payment. [useRegistrarActions.ts L45–L63](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarActions.ts#L45-L63) and [registrarHelpers.ts L238–L258](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarHelpers.ts#L238-L258) already support grouped record references and per-record availability for actual backend commands.

**Potential impact:** in the **all-departments** patient-aggregated view, `call/in_cabinet`, `complete`, `cancel`, and `print` can disappear from the context menu despite relevant individual records advertising them. A separate inline cancel control may still exist, so do **not** claim every path for those commands is unusable. Statuses can differ across grouped records; showing an action on **any** group member would require an explicit scope UX, not automatic batch execution on every record.

**Fail-first test:** for synthetic grouped rows containing (a) a single actionable record, (b) two records with the same permitted action, (c) mixed eligible/ineligible records, render context actions and compare with the backend permission model; verify consistent rendering and action selection/partial command semantics, especially `hasBackendAction(...)` all-vs-some policy. Add one actual all-departments view integration test and keep payment unaffected.

**Fix direction:** use the same backend-owned available-actions facts and explicit grouped-record selection/aggregation policy for menu affordances and command routing. No local queue eligibility inference, no auto-forwarding a mass command to a mixed-permission group.

### REG-FE-025 — Force-majeure mass actions target legacy doctor fields instead of canonical queue scope (P2 candidate)

**Code evidence:** [useRegistrarRowActions.ts L246–L252](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarRowActions.ts#L246-L252) opens the force-majeure modal with `specialistId: row.doctor_id || row.specialist_id || null` even when the queue read model includes `queue_owner_kind`, `queue_owner_id` and `daily_queue_id`, passed through in [registrarQueueAdapter.ts L65–L73](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarQueueAdapter.ts#L65-L73). The adapter does **not** populate `doctor_id` from the canonical queue owner. [ForceMajeureModal.tsx L65–L80 and L109–L115 / L143–L149](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/registrar/ForceMajeureModal.tsx#L65-L149) uses this `specialistId` to preview waiting entries and submit **mass transfer or cancellation with refunds**. Backend [force_majeure.py L142–L205](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/force_majeure.py#L142-L205) defines specialist-scoped operations requiring Admin/Registrar; backend registrar row-owner resolver explicitly distinguishes doctor-owned and resource-owned queues ([_queue_ops.py L352–L386](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_integration/_queue_ops.py#L352-L386)).

**Potential impact:** for canonical queue rows with only `queue_owner_id`, the modal can receive null specialist ID, produce no preview, and still offer confirmation actions that the API may reject; for rows containing a legacy doctor ID not matching the actual resource/queue owner, the UI may target a **different doctor's entire queue**. No unsafe mass operation has been reproduced or observed; server validates its own specialist scope and permissions, but the frontend selection is not authoritative.

**Fail-first test:** use a synthetic doctor-owned row (`queue_owner_kind:'doctor',queue_owner_id:7`, missing `doctor_id`), a resource-owned row (`queue_owner_kind:'resource',queue_owner_id:7`, incidental `doctor_id:99`), and aggregated multi-owner row. Assert the modal only opens for a *validated, unambiguous specialist scope* and never derives a target from a patient/legacy field. Backend integration tests must verify what resource-owned and mixed queues permit, and that the dry-run and POST operate on the **same** authorized scope.

**Fix direction:** do not fix this by blindly mapping `queue_owner_id` to `specialist_id`: a resource ID is not a doctor ID. Confirm a backend endpoint contract supporting the relevant owner axis or suppress this action for unsupported scopes. This is a high-impact **queue ownership/payment** domain even though currently categorized provisionally P2: run mandatory repository gate and require explicit safe scope confirmation before implementation.

### REG-FE-026 — Context-menu reschedule option hidden for canonical queue rows (P3 candidate)

**Code evidence:** [AppointmentContextMenu.tsx L162–L168](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/tables/AppointmentContextMenu.tsx#L162-L168) checks `hasBackendAction(row,'reschedule','can_reschedule')`. Canonical [_registrar_available_actions in backend _helpers.py L179–L215](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_integration/_helpers.py#L179-L215) does **not** advertise `reschedule`, and its queue serializer [_queue_ops.py L1213–L1251](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_integration/_queue_ops.py#L1213-L1251) does not serialize `can_reschedule`. The frontend [registrarQueueAdapter.ts L95–L103](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarQueueAdapter.ts#L95-L103) also omits any such flag. Meanwhile inline table control [appointmentsTableColumns.tsx L1285–L1289 and L1464–L1469](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/tables/appointmentsTableColumns.tsx#L1285-L1469) computes `canReschedule` from selected status values and calls the registrar reschedule dialog.

**Potential impact:** the same row may offer "Перенести" as an inline table button but never in the context menu. This is an affordance/consistency issue, not proof of incorrect rescheduling or permission escalation. Correct action eligibility and the backend contract should be resolved before surfacing more options.

**Fail-first test:** render one synthetic eligible row from the canonical `/registrar/queues/today` read model and compare inline/menu availability; assert consistent, backend-authorized rescheduling affordances. Include a status/role where reschedule should *not* be offered; do not assert all `waiting` records are inherently eligible.

**Fix direction:** agree a canonical reschedule eligibility/command contract (or remove the redundant menu item), and make both presentation surfaces consume it rather than relying on ad hoc client-side status tests.

### Group 3 focused review — registrar actions (2026-10-30)

**Primary files read at `main` SHA `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`:** [useRegistrarRowActions.ts](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarRowActions.ts#L1-L269) and [useRegistrarActions.ts](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarActions.ts#L1-L135). **Read-only cross-checks:** `registrarHelpers.ts`, `AppointmentContextMenu.tsx`, `appointmentsTableContracts.ts`, `appointmentsTableColumns.tsx`, `registrarAggregation.ts`, `registrarQueueAdapter.ts`, `ForceMajeureModal.tsx`, `RegistrarDialogsLayer.tsx`, `useRegistrarData.ts`, `CardiologistPanelUnified.tsx`, backend `registrar_wizard/_visits.py`, `registrar_integration/_helpers.py`, `registrar_integration/_queue_ops.py`, `force_majeure.py`, focused `useRegistrarRowActions.test.ts` and `useRegistrarActions.test.ts`, `logger.ts`. No runtime tests executed.

**Existing findings corroborated, not duplicated:** REG-FE-014 (context-menu success after null), REG-FE-015 (partial batch no reconciliation), REG-FE-017 (CancelDialog resolved-`null` false acknowledgement). A meaningful **positive** is that `runRegistrarRecordAction` routes all recognized statuses through one backend `/registrar/records/actions` command API and checks record refs and backend actions before dispatch ([useRegistrarActions.ts L45–L64](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarActions.ts#L45-L64)). `handlePayment` explicitly requires a successful payment summary and deliberately keeps committed payment separate from refresh errors ([L85–L94](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarActions.ts#L85-L94)). Backend has per-item role, lifecycle and rollback protections ([_visits.py L853–L1123](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_wizard/_visits.py#L853-L1123)). None of these prove production acceptance by themselves.

**Privacy note for REG-FE-013, same sanitizer root cause:** [useRegistrarRowActions.ts L66–L74](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarRowActions.ts#L66-L74) logs a `patient` key with the full name; [L86–L99 / L114–L135 / L175–L177](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarRowActions.ts#L86-L177) logs the entire row object in `logger.info` on view/payment/call/complete/context-edit actions. [logger.ts L15–L42 and L101–L140](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/utils/logger.ts#L15-L140) does not list bare `patient` nor `patient_fio` as PHI field aliases; it truncates objects with >15 keys, but narrower synthetic row objects may expose these fields. `logger.info` emits only in development by default. Add synthetic data examples to the same privacy batch; do not claim production disclosure or create a duplicate finding.

**Unlogged/needs product contract:** the table branches invoke status actions without `await` ([useRegistrarRowActions.ts L101–L135](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarRowActions.ts#L101-L135)); existing tests explicitly pin this behavior, and `updateAppointmentStatus` catches failures and emits error toasts. Rapid repeated clicks *may* send overlapping actions, but the backend's transition rules and idempotency contract must be exercised before logging a discrete duplicate-command defect. No P0/P1 was established.


### REG-FE-027 — Welcome morning doctor summary merges unrelated owners and mislabels row counts (P2 candidate)

**Code:** [WelcomeView.tsx L205–L280](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L205-L280) builds its `doctorMap` from `appt.doctor_id || appt.specialist_id`, uses `Врач #${doctorId}` when no name exists, and increments `patientCount` **once per record** while labelling it `Пациентов`. Canonical [registrarQueueAdapter.ts L53–L75](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/registrarQueueAdapter.ts#L53-L75) preserves `queue_owner_kind`, `queue_owner_id`, `daily_queue_id`, `patient_id` but does not synthesize a `doctor_id` from the surrounding specialty bucket. Backend [_queue_ops.py L352–L432](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_integration/_queue_ops.py#L352-L432) distinguishes doctor/resource owners.

**Risk:** canonical doctor/resource entries lacking legacy IDs may be merged into a bogus "Врач #undefined" summary; one patient with two records is counted twice as two "patients". `hasQueue` is computed but not rendered here, so do not claim a false open/closed status is displayed.

**Fail-first test:** render synthetic rows from two doctor-owned queues, a resource-owned queue, an unknown owner, and one patient with two records. Assert owner groups are not collapsed and counts use distinct patients or are accurately labelled as record counts. **Repair:** use canonical owner-aware backend presentation facts (or a typed read-model summary), never infer doctor from queue bucket; clarify scope/date and unknown-owner treatment.

### REG-FE-028 — Welcome filtered-no-match screen falsely says queue is empty (P2 candidate)

**Code:** [WelcomeView.tsx L530–L561](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L530-L561) marks empty when `!appointmentsLoading && dataSource==='api' && filteredAppointments.length===0`; [L591–L615](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L591-L615) shows "Сегодня пока нет записей"/"Создать первую запись". The parent supplies both raw `appointments` and filtered rows ([RegistrarPanel.tsx L350–L395](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/RegistrarPanel.tsx#L350-L395)); main [WorklistView.tsx L213–L269](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WorklistView.tsx#L213-L269) correctly differentiates "nothing matched" vs "no entries". Existing [registrarWorklistRows.test.ts L328–L397](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/__tests__/registrarWorklistRows.test.ts#L328-L397) tests the scope fact, but it is not wired into Welcome.

**Risk:** a failed search or narrow status filter can imply there are no patients and invite an unnecessary new registration. Distinct view surface from already fixed Worklist empty-state behavior.

**Fail-first test:** `appointments.length>0`, `filteredAppointments=[]`, `dataSource='api'`, valid auth; assert "Ничего не найдено" and no first-record text. For a genuinely empty response, assert proper empty queue CTA. **Repair:** share the backend-derived scope classification/view-model facts with Welcome, not duplicated heuristics.

### REG-FE-029 — Primary queue load failure is invisible in Welcome's empty history (P2 candidate)

**Code:** [WelcomeView.tsx L527–L545](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L527-L545) shows `DataSourceIndicator` only when `appointments.length>0`, and its empty-state condition requires `dataSource==='api'`. Table is displayed only when loading or `filteredAppointments.length>0` ([L618–L628](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L618-L628)). Thus with initial `dataSource='error'`, no loading and no rows, there is no dedicated failure/retry state. [WorklistView.tsx L213–L232](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WorklistView.tsx#L213-L232) has one; [useRegistrarWorklistData.ts L114–L136](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L114-L136) preserves this primary-error distinction.

**Risk:** staff may see a blank history region on an otherwise rendered dashboard, without knowing API data failed to load. This does not imply a full-page crash.

**Fail-first test:** render Welcome with zero entries, `dataSource='error'`, `appointmentsLoading=false`, assert visible failure text and retry invoking `loadAppointments`; also cover a previously loaded stale sample. **Repair:** use shared Worklist-style error/stale state and a retry control.

### REG-FE-030 — Welcome quick-filter changes discard unrelated URL scope (P2 candidate)

**Code:** [WelcomeView.tsx L389–L411](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L389-L411) uses `setSearchParams({status:'queued'})` and `setSearchParams({status:'paid_pending'})`, replacing the entire query rather than changing just `status`; the "Все записи" action [L379–L387](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L379-L387) similarly clears all query keys. [useRegistrarNavigation.ts L50–L63, L93–L112](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarNavigation.ts#L50-L112) explicitly syncs department/doctor from query keys and carefully preserves unrelated params in its `clearStatusFilter`.

**Risk:** clicking a status quick filter wipes `date`, `dept`, `doctor_id`, `q`, possibly changing which patients are shown. The status **value** mismatch is already REG-FE-004; this finding concerns the destructive URL update only.

**Fail-first test:** at `/registrar/welcome?date=2026-10-28&dept=lab&q=synthetic`, click each quick filter; verify these keys remain while `status` changes. Decide/document whether "Все записи" means clear status/search or deliberately clear all scope. **Repair:** use functional updates to `URLSearchParams` and mutate only intended keys.

### REG-FE-031 — Welcome selection checkboxes have no bulk-action consumer (P3 candidate)

**Code:** [WelcomeView.tsx L618–L680](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L618-L680) sets `showCheckboxes={true}` with a comment about bulk printing, but does not provide a selection handler or any bulk action. [EnhancedAppointmentsTable.tsx L51–L71, L183–L189](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/tables/EnhancedAppointmentsTable.tsx#L51-L189) keeps local selected rows and renders a "selected N" badge, not a bulk operation. Worklist deliberately sets `showCheckboxes={false}` ([WorklistView.tsx L285–L294](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WorklistView.tsx#L285-L294)) because the bulk action bar was removed.

**Risk:** users can select rows but cannot act on that selection. Not evidence of duplicate backend writes.

**Fail-first test:** render Welcome table, select two rows, verify either a valid bulk-print command exists and uses selection, or selection controls are absent pending product approval. **Repair:** disable orphaned checkboxes unless an authorized bulk operation is truly implemented.

### REG-FE-032 — Welcome history date can shift to the previous day outside clinic timezone (P3 candidate)

**Code:** [WelcomeView.tsx L516–L523](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L516-L523) uses `new Date(historyDate).toLocaleDateString(...)` without an explicit timezone. ISO date-only strings are parsed as UTC midnight, then displayed in the browser's local timezone, showing the previous calendar date in UTC-negative zones. Its hero subtitle [L191–L201](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L191-L201) also uses browser-local today; [dateUtils.ts L168–L180](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/utils/dateUtils.ts#L168-L180) and [WorklistView.tsx L148–L153](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WorklistView.tsx#L148-L153) honor the clinic's Asia/Tashkent time.

**Risk:** remote operator at UTC−5 can see 29 October on a history badge for 30 October while the backend targets 30 October. Display-only, not evidence of wrong queue date.

**Fail-first test:** run synthetic date display under `TZ=America/New_York` with `historyDate='2026-10-30'` and assert 30 October is shown; test clinic-midnight rollover. **Repair:** use shared Tashkent-aware date formatter; keep locale independent of timezone.

### REG-FE-033 — Default all-departments tabpanel has no accessible tab label (P3 candidate)

**Code:** [WorklistView.tsx L122–L133](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WorklistView.tsx#L122-L133) sets `role='tabpanel'` with `aria-labelledby` defined only when a department or doctor is selected. The all-departments control [Tabs.tsx L460–L482](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/navigation/Tabs.tsx#L460-L482) is a plain button outside the tablist, without an `id` or `role='tab'`; doctor/department controls are real tabs ([L490–L524, L573–L589](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/navigation/Tabs.tsx#L490-L589)).

**Risk:** screen readers may encounter a nameless tabpanel in the default view and cannot associate it with the all-departments control. Functional queue data remains unchanged.

**Fail-first test:** run axe/accessibility-tree and keyboard navigation in all-departments, department and doctor modes; check selected tab, tabpanel name, `aria-controls`, focus. **Repair:** make all-departments a coherent tab or expose the default view as a named region instead, while keeping proper accessible navigation.

### Group 4 focused review — interface (2026-10-30)

**Main source baseline:** `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`. **Primary files:** [WorklistView.tsx](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WorklistView.tsx#L1-L334), [WelcomeView.tsx](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L1-L696), [QueueView.tsx](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/QueueView.tsx#L1-L119).

**Cross-checks:** `RegistrarPanel.tsx`, `registrarQueueAdapter.ts`, `registrarWorklistRows.ts`, `useRegistrarWorklistData.ts`, `useRegistrarNavigation.ts`, `dateUtils.ts`, `EnhancedAppointmentsTable.tsx`, `ModernQueueManager.tsx`, `Tabs.tsx`, `registrarCsv.ts`, `registrarWorklistRows.test.ts`, `RegistrarPanel.contract.test.tsx`, and `frontend/e2e/registrar-ux-audit.spec.ts`. **No runtime tests were executed.**

**Previously indexed, not duplicated:** REG-FE-001 row click no-op in Worklist and Welcome; REG-FE-004 quick-filter status names; REG-FE-005 URL date/label; REG-FE-006 missing Welcome status confirmation; REG-FE-008 premature refresh toast; REG-FE-013 development PHI logging (Welcome passes full rows and a name string to `logger.info`, [L629–L661](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/WelcomeView.tsx#L629-L661), with no production disclosure asserted).

**Positive:** Worklist uses an effective counter descriptor, stale/error/retry logic and distinct no-match/empty states, and disables dead selection controls. QueueView forwards URL date/doctor/search values to ModernQueueManager and uses the existing queue update callback ([QueueView.tsx L87–L109](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/views/QueueView.tsx#L87-L109)); manager responds to date/doctor and queue updates ([ModernQueueManager.tsx L143–L211](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/queue/ModernQueueManager.tsx#L143-L211)). No new separately evidenced defect in QueueView itself in this bounded pass. Existing registrar UX E2E [L178–L218](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/e2e/registrar-ux-audit.spec.ts#L178-L218) checks overflow options and roles, not the missing group-4 regressions.


### REG-FE-034 — Malformed 200 queue read-model responses can appear as valid empty queues (P2 candidate)

**Code evidence:** [useRegistrarWorklistData.ts L248–L318](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L248-L318) accepts an HTTP 200 response as `Record<string,unknown>`, tests for `Array.isArray(data.queues)` and if false iterates other object keys in a **legacy-format fallback**. A response such as `{queues:null,error:'temporary issue'}`, `{message:'bad envelope'}`, or `{other:[]}` creates zero `appointmentsData` and then dispatches `LOAD_EMPTY` at L309–L314, marking it a valid empty queue. The canonical endpoint [registrar_integration/_today_queues.py](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_integration/_today_queues.py#L1-L85) returns an envelope with a `queues` collection, not arbitrary arrays of department keys. The separate [api/queue.ts L80–L85](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/api/queue.ts#L80-L85) client calls `mapQueuePayloadDto`, but that adapter [api/mappers/queue.ts L65–L70](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/api/mappers/queue.ts#L65-L70) converts `null`/non-object into `{queues:[]}` and shallow-casts any object without validating `queues`; [useQueueManager.ts L75–L85 and L189–L202](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/hooks/useQueueManager.ts#L75-L202) can subsequently manufacture an empty selection from the invalid/missing queue set.

**Potential impact:** an unexpectedly shaped HTTP 200 payload (API contract regression, proxy, or bad deploy) is presented as a truthful empty clinical worklist instead of a load failure; a registrar may think there are no waiting patients. This is **not** evidence that the live backend currently produces malformed 200 responses; test with controlled synthetic payloads. Do not confuse with REG-FE-029 (Welcome does not display the **correct** error state) or REG-FE-007 (429 rate limiting).

**Fail-first tests:** for `useRegistrarWorklistData`, mock 200 responses `{queues:null}`, `{message:'unexpected'}`, `{other:[]}` and check the hook emits `dataSource='error'` on a primary fetch, retains existing rows as `stale` on a subsequent fetch, and does not claim authoritative empty queue; separately test `{queues:[]}` as the valid empty response. For `fetchQueuesToday` / `mapQueuePayloadDto`, reject null and missing/nonarray `queues`; confirm backend contract fixtures and nonbreaking intentionally supported formats before deleting any compatibility path. Include frontend API contract and backend `/registrar/queues/today` response test.

**Fix direction:** validate the canonical envelope once at the API boundary, propagate typed errors to the existing stale/error UI, and remove or explicitly gate the old arbitrary-key fallback only after its intended support is verified. Backend remains SSOT for queue rows and ordering; React only interprets the schema.

### REG-FE-035 — Queue manager does not discard late snapshots after doctor/date switch (P2 candidate)

**Code evidence:** [useQueueManager.ts L181–L230](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/hooks/useQueueManager.ts#L181-L230) invokes `fetchQueuesToday(targetDate)`, synchronously picks the requested specialist queue and then unconditionally calls `setQueueData(queue)`, `setStatistics(...)`, and `setLoading(false)`, with no request sequence, AbortSignal, doctor/date identity check or unmount guard. [ModernQueueManager.tsx L102–L105 and L143–L170](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/queue/ModernQueueManager.tsx#L102-L170) derives current `effectiveDoctor/effectiveDate`, creates `loadQueue` callback per selection and reloads on change; [L172–L211](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/queue/ModernQueueManager.tsx#L172-L211) also schedules polling, WebSocket and local queue-event loads. The corresponding [useQueueManager.resourceAxis.test.ts L100–L167](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/hooks/__tests__/useQueueManager.resourceAxis.test.ts#L100-L167) tests specialist/resource queue matching but has no two-overlapping-request out-of-order test. The separate **Worklist** has a latest-request guard ([useRegistrarWorklistData.ts L183–L225 and L250–L253](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L183-L253)); its REG-FE-020 concerns a shared in-flight/cooldown flag, not this queue-manager result race.

**Potential impact:** start fetch A for doctor/day A; change selection to doctor/day B and fetch B; B resolves first and shows B, then A resolves and overwrites displayed entries/stats even though the controls still show B. This risks calling or opening a workflow while looking at misleading queue data; backend command IDs still receive the selected specialist and have server-side validation, so **do not claim a wrong backend record was mutated** based on this race alone. A late older `finally` can also clear shared `loading` while a newer fetch is still pending.

**Fail-first test:** in a `useQueueManager` hook test, mock `api.get('/registrar/queues/today')` with deferred A and B payloads, invoke `loadQueueSnapshot` for different specialist IDs and days, resolve B then A, and assert `queueData`, `statistics`, loading state and the manager display remain bound to B. Run an analogous polling/selection-change scenario. Positive resource-axis tests must remain green.

**Fix direction:** introduce a request epoch or abort/token bound to the requested doctor/day and only accept the current response; adopt consistent loading semantics for overlapping requests. Keep server queue-owner selection and `routing_specialists` resource handling intact rather than replacing it with a client-made doctor↔resource map.

### Group 5 focused review — API and integration (2026-10-30)

**Primary main SHA:** `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`. **Named source:** [api/registrar.ts](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/api/registrar.ts#L1-L254). **Related active API/read/action surfaces:** `api/client.ts`, `api/queue.ts`, `api/mappers/queue.ts`, `useRegistrarActions.ts`, `useRegistrarWorklistData.ts`, `useQueueManager.ts`, `ModernQueueManager.tsx`, `RegistrarPanel.tsx`. **Selectors and price approvals reviewed:** `hooks/useRegistrarApi.ts`, `PriceOverrideApproval.tsx`, `IntegratedDoctorSelector.tsx`, `IntegratedServiceSelector.tsx` with their relevant source locations and current import-site search. **Backend:** `registrar_integration/_services_doctors.py`, `registrar_integration/_today_queues.py`, `registrar_wizard/_cart.py`, `registrar_wizard/_visits.py`, `qr_queue/_queue_ops.py`, `services/qr_queue/_queue_ops.py`, `queue.py`, and `registrar_integration/_queue_ops.py`. **Tests read:** `api/__tests__/registrarDoctors.test.ts`, `api/__tests__/registrarServices.contract.test.ts`, `api/__tests__/queue.test.ts`, `pages/registrar/__tests__/useRegistrarWorklistData.test.ts`, `hooks/__tests__/useQueueManager.resourceAxis.test.ts`, `pages/__tests__/PriceOverrideApproval.contract.test.tsx`, and backend queue resource contract tests. **No runtime/unit/E2E tests executed**.

**Verified positive alignments (source only):**

- `api/registrar.ts` requests for `/registrar/price-overrides`, `/registrar/price-override/approve`, `/registrar/doctors`, and `/registrar/services` correspond to backend routes; the price-override list has `available_actions`/can flags and the mutation returns a 2xx success object after DB commit or raises HTTP errors ([backend _cart.py L1185–L1359](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_wizard/_cart.py#L1185-L1359)). No new confirmed price-command route mismatch or frontend retry-triggered duplicate-write defect was established.
- `fetchRegistrarServices(targetDate)` explicitly transmits `target_date`; backend [services_doctors.py L17–L76](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/registrar_integration/_services_doctors.py#L17-L76) resolves resource-routing for the correct booking/clinic day. `registrarServices.contract.test.ts` has source-level tests for the date and doctor-eligibility DTO contract; `registrarDoctors.test.ts` checks doctor normalization.
- Central `api/client.ts` handles token and CSRF retries, including a bounded 401 refresh replay and bounded CSRF-specific 403 recovery ([L465–L600](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/api/client.ts#L465-L600)). Both are authorization/CSRF rejection contexts, not evidence of automatic retry after a successful payment commit or a generic network timeout. Do not claim a duplicate payment was observed.
- Legacy specialist ID passed to [QRQueueService.call_next_patient](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/services/qr_queue/_queue_ops.py#L141-L213) has a documented resource-owned queue resolver via `resolve_registry_tag_queue_for_specialist`; backend route [qr_queue/_queue_ops.py L41–L73](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/backend/app/api/v1/endpoints/qr_queue/_queue_ops.py#L41-L73) uses this service. **Do not log an unsupported wrong-resource-target issue here**. Existing tests `useQueueManager.resourceAxis.test.ts` cover matching the legitimate resource queue.
- The `IntegratedServiceSelector` contains synthetic `DEMO_SERVICES` fallback on empty/failed API ([IntegratedServiceSelector.tsx L126–L183](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/registrar/IntegratedServiceSelector.tsx#L126-L183)); `IntegratedDoctorSelector` uses `Promise.all` for two metadata reads ([L73–L100](https://github.com/drsapaev/final/blob/22b21a8b7c3c0b9b56f4e388c35e329a4321f768/frontend/src/components/registrar/IntegratedDoctorSelector.tsx#L73-L100)). Current repository code search exposed declarations and the `useRegistrarApi` wrappers but **no active imports of these two components into the current registrar route**. Therefore these are **dormant/conditional risk**, not newly numbered production-path defects. Before reuse, require removal of synthetic fallback for real booking and distinct error handling for optional settings. Do not invent reachability or assume DEMO services were used for a real patient.
- Previously logged REG-FE-014/015/017 (record-command outcomes and partial batch), REG-FE-018 (swallowed post-wizard refresh errors), REG-FE-020/021 (Worklist concurrency) and REG-FE-025 (force-majeure owner target) remain distinct and are **not** duplicated by these API integration findings.

**Five-group inventory outcome:** **SOURCE REVIEW COMPLETE / REPRODUCTIONS PENDING.** All REG-FE issues are provisional until fail-first focused tests or equivalent controlled reproduction. No P0/P1 has been demonstrated, no app/test/backend files edited, no CI/build/test results claimed. Next stage is dedup/priority triage and small separate fix PRs, with mandatory gate for queue ownership/fairness, RBAC, payment, clinical lifecycle or API contracts.

### REG-FE-036 — Real patient numeric IDs from 1000 upward are silently excluded from hydration (P2 candidate)

**Code evidence:** [useRegistrarData.ts L218–L235](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/useRegistrarData.ts#L218-L235) returns null for every numeric `patientId >=1000`, assuming demo. [useRegistrarData.ts L267–L301](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/useRegistrarData.ts#L267-L301) depends on that call to hydrate missing patient name/phone/sex/address. [patients.ts L57–L69](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/api/patients.ts#L57-L69) has no comparable ID ceiling. Source tests [useRegistrarData.focusRefresh.test.tsx L82–L115](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/__tests__/useRegistrarData.focusRefresh.test.tsx#L82-L115) cover focus refresh, not high patient IDs.

**Potential impact / scope:** For an actual patient row with ID=1001 and incomplete display/gender read-model, the UI permanently skips the available patient GET and leaves missing/different profile facts. Real-ID scenario requires test fixture; no evidence that all >1000 IDs are demos.

**Synthetic fail-first and safe direction:** Synthetic patient ID 1001 and missing display contract, expect GET and correct patient; demo behavior must be an explicit backend flag, never numeric threshold.

### REG-FE-037 — Catalog revalidation lacks latest-request protection across overlapping loads (P2 candidate)

**Code evidence:** [useRegistrarData.ts L54–L81](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/useRegistrarData.ts#L54-L81) starts independent loadIntegratedData requests via Promise.allSettled; [useRegistrarData.ts L118–L151](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/useRegistrarData.ts#L118-L151) commits any fulfilled doctors/departments/services result without request epoch/abort. Focus/visibility revalidation is active; existing [useRegistrarData.focusRefresh.test.tsx L93–L159](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/__tests__/useRegistrarData.focusRefresh.test.tsx#L93-L159) checks single success/failure/throttle but not reversed A/B responses.

**Potential impact / scope:** Newly changed department/service/doctor settings could be reverted on screen by an earlier delayed request, including a newer reference-data refresh after wizard operations; backend remains authoritative.

**Synthetic fail-first and safe direction:** Start catalog request A, then B; resolve B followed by A with contradictory synthetic catalog; only B may update UI. Repeat silent and non-silent paths.

### REG-FE-038 — Patient deep-link loses the exact patient identity when converted into a name query (P2 candidate)

**Code evidence:** [useRegistrarNavigation.ts L145–L169](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/useRegistrarNavigation.ts#L145-L169) resolves `patientId` but writes only a textual `q=last_name first_name` into URL. [registrarWorklistRows.ts L179–L207](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/registrarWorklistRows.ts#L179-L207) matches this query against FIO, row ID and phone; it does not constrain `patient_id`. Existing test [useRegistrarNavigation.test.tsx L104–L111](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/__tests__/useRegistrarNavigation.test.tsx#L104-L111) pins the lossy name-query behavior.

**Potential impact / scope:** Two patients with identical FIO can both appear in a link meant for one patient; this is a selection/identity ambiguity, not evidence of a wrong patient mutation.

**Synthetic fail-first and safe direction:** Two distinct patient IDs with identical names; navigate to ?patientId=ID, confirm the worklist preserves exact ID scope or clearly states broad name search; no name-to-ID guessing.

### REG-FE-039 — Out-of-order patient deep-link lookups can leave search for the wrong URL patient (P2 candidate)

**Code evidence:** [useRegistrarNavigation.ts L151–L183](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/useRegistrarNavigation.ts#L151-L183) launches async `getPatient(patientIdFromUrl)` inside effect and unconditionally `setSearchParams` after await, without cleanup, cancellation or a request generation check. Tests [useRegistrarNavigation.test.tsx L104–L118](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/__tests__/useRegistrarNavigation.test.tsx#L104-L118) cover one successful fetch or 404, not A/B races.

**Potential impact / scope:** Rapidly changing patientId can leave q matching an outdated patient despite the current URL indicating the new ID. This is UI mismatch, not evidence of backend reassignment.

**Synthetic fail-first and safe direction:** Deferred GET A/B, navigate from A to B while mounted, resolve B then A; search remains B, and stale A failure must not override state.

### REG-FE-040 — Reschedule dialog retains stale date/time between patient records (P2 candidate)

**Code evidence:** [RescheduleSlots.tsx L47–L65](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/views/RescheduleSlots.tsx#L47-L65) keeps customRescheduleDate/customRescheduleTime in component state, but `ModernDialog onClose={onClose}` does not call resetForm. Resets only after confirmation at [RescheduleSlots.tsx L90–L100](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/views/RescheduleSlots.tsx#L90-L100) and [RescheduleSlots.tsx L159–L169](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/views/RescheduleSlots.tsx#L159-L169); same component is mounted continuously inside [RegistrarDialogsLayer.tsx L130–L144](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/views/RegistrarDialogsLayer.tsx#L130-L144) structure.

**Potential impact / scope:** Cancel modal for A after entering 2026-11-10, reopen for B, date can still be prefilled; a careless confirmation could reschedule B to an unintended date.

**Synthetic fail-first and safe direction:** Open modal for A, type date/time, close without submission, open for B; expect blank or explicit B-specific values. Reset by target/open state, preserve only current user edit.

### REG-FE-041 — Rescheduling a grouped patient row can move only the first visit while hiding the group (P2 candidate)

**Code evidence:** [useRegistrarReschedule.ts L23–L29](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/useRegistrarReschedule.ts#L23-L29) chooses `visit_ids[0]` even for multiple visits. [RescheduleSlots.tsx L159–L171](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/views/RescheduleSlots.tsx#L159-L171) sends one `rescheduleVisit`, then removes the row; [useRegistrarReschedule.ts L31–L81](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/useRegistrarReschedule.ts#L31-L81) removes IDs from the grouped row, including all `visit_ids`. Prior REG-FE-009 covers cross-namespace optimistic removal, but not the separate first-visit-only command semantics.

**Potential impact / scope:** A grouped patient with two visits may get one visit rescheduled and other visit visually removed until refresh, misleading staff about the changed appointments. Requires a fixture proving grouped rows can reach this action.

**Synthetic fail-first and safe direction:** Synthetic row visit_ids=[101,102], click reschedule; assert both are intentionally handled through a backend-authorized group contract or require explicit visit selection and preserve untouched 102.

### REG-FE-042 — Selected doctor with no matching queue appears to have an empty queue instead of no queue (P2 candidate)

**Code evidence:** [useQueueManager.ts L75–L82](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/hooks/useQueueManager.ts#L75-L82) returns null for missing payload queues, and [useQueueManager.ts L181–L203](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/hooks/useQueueManager.ts#L181-L203) replaces any null pickQueueForDoctor result with invented `{id:Number(specialistId), entries:[], stats:null}`. [QueueTable.tsx L161–L187](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/queue/QueueTable.tsx#L161-L187) intentionally distinguishes `queueData=null` («Очередь не найдена») from a known queue with zero entries («Очередь пуста»). Existing source test [QueueManager.contract.test.tsx L38–L59](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/queue/__tests__/QueueManager.contract.test.tsx#L38-L59) checks explicit selection only.

**Potential impact / scope:** Missing/unconfigured doctor queue and a genuinely zero-patient queue become indistinguishable; this may mask wrong specialist or resource ownership.

**Synthetic fail-first and safe direction:** Backend returns queues for doctor B only, select doctor A; assert a truthful no-queue state, without invented queue ID or mutating server data.

### REG-FE-043 — Inline Cancel/Reschedule controls bypass backend-driven action availability (P2 candidate)

**Code evidence:** [appointmentsTableColumns.tsx L1263–L1275](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/appointmentsTableColumns.tsx#L1263-L1275) correctly uses `getBackendActionAvailability` for payment, call, print, complete and other actions; immediately after, [appointmentsTableColumns.tsx L1276–L1289](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/appointmentsTableColumns.tsx#L1276-L1289) computes `canCancel`/`canReschedule` from local status strings. [appointmentsTableContracts.ts L55–L71](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/appointmentsTableContracts.ts#L55-L71) already exposes fail-closed backend action lookup.

**Potential impact / scope:** Commands can be offered for a record whose backend denied them, or hidden despite an explicit backend allowance. Server must still reject unauthorized mutation, so this is a contract/presentation defect only.

**Synthetic fail-first and safe direction:** Same status, conflicting server `available_actions` / capability flags; buttons follow backend. Review aggregated record actions and undefined capabilities; no optimistic permission.

### REG-FE-044 — Registrar dashboard revenue is calculated from appointments rather than canonical payments (P2 candidate)

**Code evidence:** [WelcomeView.tsx L287–L299](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/views/WelcomeView.tsx#L287-L299) passes loaded `appointments` to active ModernStatistics. [ModernStatistics.tsx L191–L223](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/statistics/ModernStatistics.tsx#L191-L223) filters `payment_status==='paid'` and sums `payment_amount || cost` without net refunds, actual settlement identities or reconciliation, while the same component labels this as revenue.

**Potential impact / scope:** Dashboard can overstate/understate income for partial payments, refunded receipts and multiple records per patient. This is not the actual cash register; no database alteration claimed.

**Synthetic fail-first and safe direction:** Synthetic one patient with partial, fully paid, refunded payments and duplicate appointment records; compare read-model with backend server-owned net settled revenue or relabel the card as non-financial record estimate.

### REG-FE-045 — CSV export can lose service labels and zero-price values (P3 candidate)

**Code evidence:** [registrarCsv.ts L57–L79](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/registrarCsv.ts#L57-L79) applies `row.services.join('; ')` even when service DTO elements are objects, producing `[object Object]`; `row.cost || row.total_amount || ''` treats explicit zero as absent. Active table calls generateCSV(filteredData) at [EnhancedAppointmentsTable.tsx L89–L101](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/EnhancedAppointmentsTable.tsx#L89-L101) and read models can carry service objects.

**Potential impact / scope:** Exported report can have illegible service names and blank cost for free services, without affecting saved appointments.

**Synthetic fail-first and safe direction:** Synthetic rows with services [{name:'Echo',code:'K2'}] and cost=0; assert meaningful service labels and numeric zero are preserved. Use presentation-only formatting.

### REG-FE-046 — Formula neutralizer does not inspect leading whitespace/control characters in CSV cells (P3 candidate)

**Code evidence:** [registrarCsv.ts L82–L95](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/registrarCsv.ts#L82-L95) uses `/^[=+\-@]/` against raw escaped text and prefixes apostrophe only on immediate match. An untrusted name/note beginning with tab/CR or spaces before formula marker is not neutralized by this predicate. Direct `=SUM(...)` is protected; applicability depends on spreadsheet import normalization.

**Potential impact / scope:** Possible spreadsheet formula interpretation if a consumer strips/ignores leading control whitespace. No exploit or running formula was observed; this is conditional and requires an isolated Excel/LibreOffice reproduction.

**Synthetic fail-first and safe direction:** Synthetic names with '=1+1', '\t=1+1', '\r=1+1', ' =1+1' and ordinary strings; validate safe spreadsheet import while preserving human-readable text. Security gate before code change.

### REG-FE-047 — Statistics Export button is wired to a logger-only callback (P3 candidate)

**Code evidence:** [WelcomeView.tsx L287–L298](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/views/WelcomeView.tsx#L287-L298) passes onExport={()=>logger.info('Экспорт статистики')} to mounted `ModernStatistics`, whose button [ModernStatistics.tsx L401–L410](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/statistics/ModernStatistics.tsx#L401-L410) invokes onExport. This is different from the separate appointment CSV export in EnhancedAppointmentsTable.

**Potential impact / scope:** Registrar clicks Export in analytics and receives no downloaded report or visible feedback; not evidence that the main appointment export is broken.

**Synthetic fail-first and safe direction:** Render WelcomeView stats and trigger export, assert actual stats artifact generation/download or remove the unsupported control explicitly.

### REG-FE-048 — Registrar shortcuts can conflict with browser tab switching and select focus (P3 candidate)

**Code evidence:** [useRegistrarHotkeys.ts L48–L57](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/useRegistrarHotkeys.ts#L48-L57) checks INPUT/TEXTAREA only, not SELECT or contentEditable; [useRegistrarHotkeys.ts L74–L93](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/useRegistrarHotkeys.ts#L74-L93) calls setActiveTab on Ctrl+2/3/4 without preventDefault. Existing [useRegistrarHotkeys.modalGate.test.tsx L42–L87](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/__tests__/useRegistrarHotkeys.modalGate.test.tsx#L42-L87) checks modal handling and INPUT but not focused select or native Ctrl+digit conflict.

**Potential impact / scope:** Ctrl+2 may select a browser tab and update hidden registrar state; keyboard use in select/custom editors is not isolated. Browser handling varies, so confirm experimentally.

**Synthetic fail-first and safe direction:** Synthetic keyboard focus on SELECT/contentEditable and Ctrl+2; verify no hidden navigation and no unintended browser conflict or scope opt-in.

### REG-FE-049 — ModernDialog delayed focus has no cancellation across modal lifecycle (P3 candidate)

**Code evidence:** [ModernDialog.tsx L57–L106](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/dialogs/ModernDialog.tsx#L57-L106) sets a 100-ms timeout to focus the first interactive control on open, but cleanup only removes keydown listener and overflow style. Because dialogRef can reference a quickly reopened instance, an old timeout can target a newer modal.

**Potential impact / scope:** On rapid close/reopen of registrar dialogs, delayed focus may jump after user interaction. On a closed/unmounted dialog ref is null, so no unconditional focus leak claimed.

**Synthetic fail-first and safe direction:** Fake timers: open A, close, reopen B and interact before 100ms; verify only current modal controls focus and timers are cancelled on cleanup.

### REG-FE-050 — Text/date/status sorting is broken by numeric-only comparator (P2 candidate)

**Source evidence:** [appointmentsTableColumns.tsx L867–L872](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/appointmentsTableColumns.tsx#L867-L872), [appointmentsTableColumns.tsx L1095–L1101](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/appointmentsTableColumns.tsx#L1095-L1101) and [appointmentsTableColumns.tsx L1191–L1196](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/appointmentsTableColumns.tsx#L1191-L1196) mark patient_fio, appointment_date, status sortable. Yet [appointmentsTableContracts.ts L230–L259](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/appointmentsTableContracts.ts#L230-L259) compares only `Number(aVal)` and `Number(bVal)`; on `'Иванов ...'`, `'2026-11-01'`, `'waiting'`, both become NaN so neither comparison succeeds. Canonical DataTable propagates header sorts to this comparator at [DataTable.tsx L700–L710](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/ui/DataTable.tsx#L700-L710). Existing [appointmentsTableContracts.test.ts L26–L57](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/__tests__/appointmentsTableContracts.test.ts#L26-L57) pins only numeric cost/queue sorting, not text/date/status.

**Impact and uncertainty:** The UI advertises A–Z, date ascending and status ordering but may retain prior input order. Clinically relevant queue ordering remains backend-owned; no queue-number mutation claimed.

**Synthetic fail-first and safe direction:** Synthetic reversed Cyrillic and Latin surnames, ISO dates across months, canonical statuses: ascending/descending expected order, stable ties. Preserve numeric price/queue sorting, with missing values handled explicitly and clinic timezone not silently reinterpreted.

### REG-FE-051 — Filtering or dataset refresh on a later page can show a false empty table (P2 candidate)

**Source evidence:** [useAppointmentsTableState.ts L30–L40](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/useAppointmentsTableState.ts#L30-L40) starts `currentPage` independently; [useAppointmentsTableState.ts L70–L86](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/useAppointmentsTableState.ts#L70-L86) recomputes `filteredData` and slices with stale `(currentPage-1)*20`, with no effect or clamp when matches/data change. [EnhancedAppointmentsTable.tsx L145–L169](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/EnhancedAppointmentsTable.tsx#L145-L169) changes filterConfig; [EnhancedAppointmentsTable.tsx L203–L234](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/EnhancedAppointmentsTable.tsx#L203-L234) passes the empty `paginatedData` to DataTable and shows page controls only if `totalPages>1`.

**Impact and uncertainty:** If user selected page 3 with >=41 records then searches a result subset of 2, the table reports no data even though 2 records match. On registrar screens this can falsely imply absence of booked patients; the backend is not changed.

**Synthetic fail-first and safe direction:** RTL render 45 synthetic visits, navigate page3, search for exactly two, assert two rows visible and page reset to1; repeat load replacing 45 rows with 2 and status selector. Check no blank scroll/phantom page.

### REG-FE-052 — Unrecognized canonical queue lifecycle statuses are mislabeled as Scheduled (P2 candidate)

**Source evidence:** [queue_status.py L13–L29](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/services/queue_status.py#L13-L29) defines `in_service`, `diagnostics`, `incomplete`, `rescheduled` as canonical statuses; [_queue_ops.py L1239–L1254](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/registrar_integration/_queue_ops.py#L1239-L1254) publishes `status=canonical_status`, and [registrarQueueAdapter.ts L40–L44](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/registrarQueueAdapter.ts#L40-L44) / [registrarQueueAdapter.ts L84–L91](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/registrarQueueAdapter.ts#L84-L91) retain it. [appointmentsTableColumns.tsx L81–L218](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/appointmentsTableColumns.tsx#L81-L218) lacks these statuses and falls back to `statusConfig.scheduled` for ALL unknown statuses. Renderer is active in both registrar Welcome/Worklist table.

**Impact and uncertainty:** An already-rescheduled, incomplete or diagnostics entry can be shown as a fresh scheduled appointment. This is presentation misinformation; no clinical action was executed in review.

**Synthetic fail-first and safe direction:** Render each canonical status from backend queue_status.py plus unexpected future status. Assert truthful localized label (or explicit raw/unknown indicator), never scheduled for unrecognized values; keep legacy alias behavior.

### REG-FE-053 — Table search cannot reliably match the services visibly rendered as nested objects (P3 candidate)

**Source evidence:** [appointmentsTableContracts.ts L263–L278](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/appointmentsTableContracts.ts#L263-L278) searches `String(val)` for each top-level row field, so `String([{name:'ЭхоКГ'}]) === '[object Object]'`. The display renderer [appointmentsTableColumns.tsx L242–L271](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/appointmentsTableColumns.tsx#L242-L271) explicitly supports service objects with `code` or `name`, and [appointmentsTableColumns.tsx L1000–L1025](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/appointmentsTableColumns.tsx#L1000-L1025) feeds such DTOs into the displayed service column. Existing filter test [appointmentsTableContracts.test.ts L59–L82](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/__tests__/appointmentsTableContracts.test.ts#L59-L82) covers only flat patient names.

**Impact and uncertainty:** A registrar may see a named service but receive no rows when searching that service, if no other scalar column coincidentally matches. Exact impact depends on backend service-array shape.

**Synthetic fail-first and safe direction:** Rows with services=[{name:'ЭхоКГ', code:'K11'}] and with simple strings; query service name and code; ensure displayed catalog name/codes and phone/name searches work with canonical DTOs.

### REG-FE-054 — Context menu has no intentional focus entry or menu semantics (P3 candidate)

**Source evidence:** [AppointmentContextMenu.tsx L85–L107](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/AppointmentContextMenu.tsx#L85-L107) adds global outside-click/Escape handlers but never focuses menu or a menu item; [AppointmentContextMenu.tsx L238–L268](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/AppointmentContextMenu.tsx#L238-L268) renders a full-screen fixed div and unlabelled nested div, and [AppointmentContextMenu.tsx L283–L314](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/AppointmentContextMenu.tsx#L283-L314) renders buttons without `role=menuitem` / appropriate menu container. Storybook [AppointmentContextMenu.stories.tsx L31–L60](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/AppointmentContextMenu.stories.tsx#L31-L60) only shows static registrar/doctor cases, no keyboard navigation contract.

**Impact and uncertainty:** Keyboard and screen-reader users can encounter a visually open action menu without predictable focus and semantic context. Browser keyboard focus may remain on the underlying row button. Actual assistive-technology behavior untested.

**Synthetic fail-first and safe direction:** RTL keyboard-only trigger, assert focus moves into menu (or accessible non-menu dialog pattern), tab/arrow/Escape navigation and focus restoration; run axe/browser keyboard smoke. Do not force menu-role pattern without implementing associated keyboard semantics.

### REG-FE-055 — Composite row keys use unstable page-relative index (P3 candidate)

**Source evidence:** [appointmentsTableContracts.ts L73–L84](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/appointmentsTableContracts.ts#L73-L84) explicitly appends `index` to row key, and [EnhancedAppointmentsTable.tsx L203–L206](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/EnhancedAppointmentsTable.tsx#L203-L206) uses it in DataTable `getRowId`. [DataTable.tsx L1074–L1078](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/ui/DataTable.tsx#L1074-L1078) passes that directly as React's `key`. Sorting, filtering and paging changes indices, so the same record's key changes even if its canonical record/queue ID did not.

**Impact and uncertainty:** Rows can remount, losing focus/inline transient state and resetting screen-reader or keyboard position during sorting/search. Including index may be compensating for duplicate IDs; removing it without a unique stable canonical record key could introduce worse collisions.

**Synthetic fail-first and safe direction:** Stable synthetic record identity across reordering and pages, check remount count and keyboard focus; separate queue-entry, visit and appointment namespaces; duplicate-ID negative test before removing index.

### Focused registrar table files source audit — 2026-11-01

**Reviewed at pinned main `a770ce3373b6e4b69f54b51723e1f2775dac4088`:** All 11 paths in `frontend/src/components/tables/`: `EnhancedAppointmentsTable.tsx`, `useAppointmentsTableState.ts`, `appointmentsTableContracts.ts`, `appointmentsTableColumns.tsx`, `AppointmentContextMenu.tsx`, `AppointmentPagination.tsx`, CSS, Storybook fixtures and three focused test files. Also read active parent renderers `WelcomeView.tsx` and `WorklistView.tsx`, `DataTable.tsx` sort/row key/keyboard contract, backend canonical queue-status vocabulary and registrar queue response shape. `AppointmentPagination.tsx` is a dormant extracted component (main EAT renders its own inline pagination); no active-specific finding without a consumer.

**New findings:** REG-FE-050–055 (3 P2, 3 P3) documented with source facts and synthetic reproduction criteria. Both sortable-column and false-empty-page root causes are directly visible in pure functions, but tests not run. The status fallback explicitly maps unknowns to `scheduled`, while server publishes canonical `in_service`, `diagnostics`, `incomplete`, `rescheduled`. `DataTable` correctly delegates sorting to the parent; defects belong to EAT's comparator/derived state, not to Datatable's delegation.

**Existing finding deepened, not duplicated — REG-FE-031:** WelcomeView enables selection (`showCheckboxes=true`) without an actionable consumer; WorklistView disables checkboxes. Within enabled EAT selection, [appointmentsTableColumns.tsx L814–L839](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/appointmentsTableColumns.tsx#L814-L839) uses `selectedRows.size === paginatedData.length` as the select-all checkbox state instead of checking membership of every current-page row; [useAppointmentsTableState.ts L115–L129](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/useAppointmentsTableState.ts#L115-L129) replaces/clears the entire internal Set when selecting/deselecting the current page. For example, select 20 on page1 then move to page2 with 20 unchecked rows: header may show checked and unchecking wipes page1. Also row selections use naked `row.id`, while DataTable rows use composite entity keys. This is an additional correctness issue **within** the currently orphaned selection UX: do not introduce bulk financial/clinical action until stable typed identity, page-scoped select-all and a real consumer exist.

**Existing finding deepened, not duplicated — REG-FE-004:** Local EAT status dropdown contains `paid`/`paid_pending` options at [EnhancedAppointmentsTable.tsx L157–L170](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/EnhancedAppointmentsTable.tsx#L157-L170) but `filterAppointmentsData` checks only `row.status`, not `row.payment_status` ([appointmentsTableContracts.ts L263–L277](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/appointmentsTableContracts.ts#L263-L277)). This is the same status-namespace mismatch already documented for Welcome quick filters. Confirm the precise desired payment-status filter semantics against the backend DTO before implementation.

**Prior table-related overlaps retained, not duplicated:** REG-FE-001 (Worklist row click logger-only), 006 (Welcome action confirmation gap), 023 (advertised unhandled schedule_next), 026 (context reschedule hidden), 031 (orphaned selection), 043 (inline cancel/reschedule bypass backend action flags), 045–046 (CSV export service/zero/formula pitfalls). `call_patient` DOES have a registrar handler at `useRegistrarRowActions.ts` L229–244; do not misreport this as dead code. Canonical DataTable already provides header `aria-sort` and Enter/Space sort handling; do not report missing table-header keyboard support.

**Release boundary:** Source-only read and documentation changes. No Vitest/Playwright/axe, local repo checkout, PowerShell agent gate, code edits, merge, staging or production actions. One future minimal fix PR per root cause, synthetic fail-first proof, mandatory repo gate when touching clinical lifecycle/queue identity/backend contract, independent review and CI.

### Supplemental full-directory source sweep — 2026-11-01 (fresh main)

**Base and method:** Pinned current main `a770ce3373b6e4b69f54b51723e1f2775dac4088`, reviewed 3-commit drift from original audit baseline `9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1`. This second pass **extends** earlier 35 candidates with REG-FE-036–049; all are SOURCE-OBSERVED/REPRO-PENDING. No synthetic runtime or browser tests were executed in this chat.

**Exhaustive file-name inventory and bounded source scans in these *direct registrar and shared registrar-connected directories*:**

| Source directory | Files in GitHub tree | Role / source-scan treatment |
| --- | ---: | --- |
| `frontend/src/pages/registrar/` | 42 | All page-local runtime files, CSS, source contract tests, views, README/design docs inspected by module/source scan; particularly useRegistrarData, navigation, reschedule, CSV |
| `frontend/src/components/registrar/` | 6 | Current ForceMajeureModal + test/CSS inspected; remaining selectors/price approval scanned but no active RegistrarPanel import established |
| `frontend/src/components/queue/` | 13 | ModernQueueManager, QueueTable, qrExpiry, QueueManagementCard, tests/CSS/stories source scanned; QueueManagementCard is not a proven registrar-rendered component (doctor-specific paths elsewhere) |
| `frontend/src/components/tables/` | 11 | Main table, action columns, helpers, pagination, tests/CSS/stories scanned; backend action flags checked |
| `frontend/src/components/wizard/` | 33 | Master and wizardUtils high-risk paths and component sources, corresponding 20 source tests, CSS/stories inspected; 3331-LOC wizard and 2343-LOC utils were **targeted, not fully branch-by-branch proven** |
| `frontend/src/components/dialogs/` | 11 | PaymentDialog, CancelDialog, PrintDialog, ModernDialog, source test, CSS and stories inspected |

**Other traceable active dependencies examined:** `RegistrarPanel.tsx`, `QueueJoin.tsx` (separate public join route), `frontend/src/components/statistics/ModernStatistics.tsx`, shared patient/visits/queue/queueResources and registrar APIs, hooks `useQueueManager`, `useQueueApi`, `useQueueWebSocket`, `useRegistrarApi`, and relevant backend registrar/refund/payment/queue contracts. These are scoped to registrar behavior; this is **not** a claim to have reviewed every general-purpose component in the 5,984-item entire GitHub tree, every transitive dependency, or every CSS selector for browser correctness.

**Excluded from active issue count:** `IntegratedServiceSelector.tsx` still contains hardcoded demo service IDs/prices and keeps them after API failure ([IntegratedServiceSelector.tsx L55–L85](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/registrar/IntegratedServiceSelector.tsx#L55-L85), [IntegratedServiceSelector.tsx L126–L183](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/registrar/IntegratedServiceSelector.tsx#L126-L183)); repository code search found no active import in RegistrarPanel/wizard, so **do not** call this a demonstrated production pricing defect. `PriceOverrideApproval.tsx` and `IntegratedDoctorSelector.tsx` likewise require reachability proof; orphan cleanup is architectural work, not an observed active UI failure. `QueueManagementCard.tsx` logs action failures without a toast ([QueueManagementCard.tsx L142–L183](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/queue/QueueManagementCard.tsx#L142-L183)), but active registrar QueueView mounts ModernQueueManager/QueueTable, not this doctor-side card; exclude from registrar bug tally without proof of a registrar consumer.

**Main drift revalidation for existing REG-FE-025:** new main `a770ce3373b6e4b69f54b51723e1f2775dac4088` includes new `useRegistrarRowActions.ts`, ForceMajeureModal and tests. Source now requires canonical doctor queue owner and `daily_queue_id` before mass action, binds pending-entry preview to owner/day/queue and `expected_entry_ids`, and synchronously guards double financial submissions; `ForceMajeureModal.test.tsx` source includes out-of-order preview, owner-conflict, bank-vs-deposit, idempotent replay cases. Prior `CONFIRMED / FIX-IN-REVIEW` is historical audit disposition. **Do not represent the old main bug as definitely still unfixed.** This read-only session did not run the tests or verify production.

**Verified protections worth retaining:** PaymentDialog uses server `payment_snapshot`, a synchronous in-flight ref and an explicit remaining-debt check; the wizard requires server quote, uses Idempotency-Key and read-back verification and has existing targeted contract tests. QueueWebSocket sends bearer JWT via subprotocol, not query-string token. Supplemental tests did not reproduce these fixes; evidence is source inspection only.

**Priority to test:** REG-FE-036 high patient-ID contract, 038/039 identity deep links, 040/041 reschedule target state/group semantics, 042 queue absent vs empty, 043 server action capability, 044 real revenue read-model; then reference data races 037 and export/keyboard/focus 045–049. Require the repository mandatory agent gate before changing queue ownership, financial read-models, patient identity, RBAC or clinical lifecycle. No code/migration/config/production edit in this docs-only PR.

### Scoped follow-up tickets — 2026-11-01 (source-to-backend verification, no code edits)

- [Issue #3819 — REG-FE-036 high patient IDs](https://github.com/drsapaev/final/issues/3819): `useRegistrarData.ts` has the `pid >= 1000` early return, but [Patient.id](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/models/patient.py#L26-L29) is a regular integer primary key with no reserved demo ID range. This **strengthens the source-level diagnosis**, but does not constitute a RED→GREEN reproduction. Status remains `SOURCE-OBSERVED / REPRO-PENDING`, provisional P2.
- [Issue #3820 — REG-FE-040/041 reschedule identity](https://github.com/drsapaev/final/issues/3820): RescheduleSlots persists user-selected fields after a dismiss; an aggregate row can contain multiple `visit_ids`, yet the UI only passes the first visit ID to [single-visit reschedule endpoint](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/visits.py#L682-L716) and then applies grouped optimistic removal. Must test both distinct modal sessions and two visits within the same patient aggregate. **Do not confuse with existing REG-FE-009 (cross-namespace ID removal).** Both retain provisional P2 and `REPRO-PENDING`.
- [REG-FE-038/039 patient ID deep links](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/useRegistrarNavigation.ts#L145-L183): source lookup resolves `patientId` but writes a FIO-based `q` with no immutable identity filter or async result epoch; backend name collision and out-of-order response tests remain outstanding, do not report a wrong-patient write without evidence.
- [REG-FE-043](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/tables/appointmentsTableColumns.tsx#L1263-L1289): inline cancel/reschedule buttons are status-driven while adjacent commands are server-action-driven. This remains UI affordance mismatch; no evidence of a backend RBAC bypass.
- **Scope & gate:** Github-only source and issue operations; implementation or test source was **not** changed. Mandatory `run_agent_gate.ps1`, Vitest, pytest, Playwright, and local build were **not run**. Separate authorized cloud coding worktree is required before touching identity/queue/clinical contracts; follow `AGENTS.md`. No merge or production deploy.

## Review coverage

### Actually inspected in first pass (source reads; not an exhaustive audit)

- `frontend/src/pages/RegistrarPanel.tsx`
- `frontend/src/pages/registrar/registrarWorklistRows.ts`
- `frontend/src/pages/registrar/registrarServiceFilter.ts`
- `frontend/src/pages/registrar/useRegistrarWizard.ts`
- `frontend/src/pages/registrar/useRegistrarNavigation.ts`
- `frontend/src/pages/registrar/useRegistrarRowActions.ts`
- `frontend/src/pages/registrar/useRegistrarHotkeys.ts`
- `frontend/src/pages/registrar/views/WorklistView.tsx`
- `frontend/src/pages/registrar/views/RegistrarDialogsLayer.tsx`
- `frontend/src/components/tables/EnhancedAppointmentsTable.tsx`
- `frontend/src/utils/registrarAggregation.ts`
- `frontend/src/utils/logger.ts`
- `frontend/src/api/registrar.ts`
- `frontend/src/components/wizard/AppointmentWizardV2.tsx`
- `frontend/src/components/wizard/wizardUtils.ts`
- `frontend/src/pages/registrar/useRegistrarActions.ts` and `useRegistrarRowActions.ts` (context action return contract)
- `backend/app/api/v1/endpoints/registrar_wizard/_visits.py` (per-record action semantics)
- `backend/app/services/registrar_doctor_eligibility.py` (write-side pin and route guards)
- `frontend/src/components/wizard/PatientStepV2.tsx`
- `frontend/src/components/wizard/CartStepV2.tsx`
- `frontend/src/components/dialogs/ModernDialog.tsx`
- `frontend/src/api/queue.ts` and `frontend/src/api/mappers/queue.ts`
- Selected wizard regression/contract tests in `frontend/src/components/wizard/__tests__/`
- `frontend/src/pages/registrar/views/WelcomeView.tsx`
- `frontend/src/pages/registrar/views/QueueView.tsx`
- `frontend/src/pages/registrar/useRegistrarWorklistData.ts`
- `frontend/src/pages/registrar/useRegistrarReschedule.ts`
- `frontend/src/pages/registrar/useRegistrarCalendar.ts`
- `frontend/src/pages/registrar/views/RescheduleSlots.tsx`
- `backend/app/api/v1/endpoints/registrar_integration/_helpers.py` and relevant `_today_queues.py` mapping (read-only contract evidence)
- Focused source-contract / worklist test files were partially inspected to identify regression-test owners.

### Agreed five-group registrar review order

Run **one bounded file group per review pass**; for each group, verify the current `main` SHA, inspect the named files and only their necessary callers/tests/backend contract, de-duplicate against existing IDs, and append source evidence + fail-first tests here. Do not implement app fixes in this audit PR.

1. **Group 1 — patient registration — SOURCE REVIEW DONE (2026-10-30), reproductions pending:** `frontend/src/pages/RegistrarPanel.tsx`, `frontend/src/pages/registrar/useRegistrarWizard.ts`, `frontend/src/pages/registrar/views/RegistrarDialogsLayer.tsx`. Added REG-FE-017–019; earlier cross-cutting issues remain pending tests.
2. **Group 2 — queues — SOURCE REVIEW DONE (2026-10-30), reproductions pending:** `frontend/src/pages/registrar/useRegistrarWorklistData.ts`, `frontend/src/pages/registrar/registrarWorklistRows.ts`, `frontend/src/pages/registrar/registrarQueueAdapter.ts`. Completed bounded read with backend number/owner validation and focused test inspection; added REG-FE-020–022.
3. **Group 3 — registrar actions — SOURCE REVIEW DONE (2026-10-30), reproductions pending:** `frontend/src/pages/registrar/useRegistrarRowActions.ts`, `frontend/src/pages/registrar/useRegistrarActions.ts`. Added REG-FE-023–026; earlier REG-FE-014/015/017 reaffirmed; REG-FE-013 cross-file privacy scope expanded.
4. **Group 4 — interface — SOURCE REVIEW DONE (2026-10-30), reproductions pending:** `frontend/src/pages/registrar/views/WorklistView.tsx`, `frontend/src/pages/registrar/views/WelcomeView.tsx`, `frontend/src/pages/registrar/views/QueueView.tsx`. Group 4 completed; added REG-FE-027–033 (Welcome summary, empty/error feedback, URL filters, dead checkboxes, date formatting and default tabpanel accessibility).
5. **Group 5 — API and integration — SOURCE REVIEW DONE (2026-10-30), reproductions pending:** `frontend/src/api/registrar.ts`, relevant clients/mappers and frontend/backend contract tests. Completed bounded API/client/backend contract read. Added REG-FE-034–035 (malformed API envelope and queue snapshot race); aligned routes, resource-call fallback and contract tests.

## Remediation plan — execute only after review triage

1. **Freeze and verify:** complete relevant review slices; fetch latest `main` and compare the old anchored evidence with the new baseline. Confirm each candidate using a fail-first focused unit/component/e2e test; close false positives without editing application code.
2. **Triage risk and ownership:** address confirmed P0/P1 before P2/P3. If any fix touches queue ownership/fairness, clinical lifecycle, payment truth, authentication or API contracts, run the repository-required execution gate and inspect canonical source, ADRs and backend tests before editing.
3. **Batch A — interaction:** `REG-FE-001`; decide desired row-click UX, add keyboard/pointer regression, smallest implementation change, review, CI.
4. **Batch B — view model/localization:** `REG-FE-002` + `REG-FE-003` only if they remain purely presentation-level and independently tested; avoid altering backend SSOT and identity.
5. **Batch C — quick filters and status semantics:** verify REG-FE-004 against canonical queue status and payment-state DTOs.
6. **Batch D — date and refresh lifecycle:** verify REG-FE-005, 007, 008 with effective-date and explicit fetch-state tests.
7. **Batch E — reschedule UI identity:** verify REG-FE-009 with cross-namespace ID collisions.
8. **Batch F — patient selection and persistence:** verify REG-FE-010 and implement an explicit profile-edit contract, if intended.
9. **Batch G — patient/visit partial saves:** verify REG-FE-011; choose safe domain ownership with a mandatory execution gate.
10. **Batch H — asynchronous wizard catalogue:** verify REG-FE-012 with out-of-order responses.
11. **Batch I — PHI-safe diagnostics:** verify/fix REG-FE-013 with synthetic logging tests.
12. **Batch J — registrar command feedback:** verify REG-FE-014/015 with failure and partial-success contract tests; mandatory gate applies if backend action semantics/queue lifecycle is changed.
13. **Batch K — prospective visit count:** verify REG-FE-016 against the same pure grouping that constructs the cart payload.
14. **Batch L — cancellation acknowledgement:** verify REG-FE-017 with a real CancelDialog + handler-level mock and explicit partial/no-op result contract.
15. **Batch M — post-save refresh:** verify REG-FE-018 with rejected/429/degraded integrated-data loads, keeping committed saves independent of refresh.
16. **Batch N — toast ownership:** verify REG-FE-019 and preserve a single save confirmation.
17. **Batch O — queue fetch concurrency and interval modal state:** verify REG-FE-020/021 with deferred network responses and fake timers; distinguish newest-sample integrity from in-flight/429 scheduling and dialog policy.
18. **Batch P — canonical queue allocation fact:** verify REG-FE-022 with backend linked/unlinked queue records and pure adapter→stats tests, run mandatory queue SSOT gate before repair.
19. **Batch Q — action menu contract and wiring:** verify REG-FE-023/024/026 (schedule-next visibility, grouped availability and reschedule affordance). Align UI with backend actions, protect role boundaries; use mandatory gate if backend contract/clinical workflow changes.
20. **Batch R — force-majeure target ownership:** verify REG-FE-025 against doctor/resource/aggregate scopes and backend dry-run+POST consistency; mandatory queue/payment execution gate before any repair.
21. **Batch S — Welcome data/summary truth:** verify REG-FE-027/028/029 with canonical owner, patient and loading/empty/error facts; no frontend business-rule guesses.
22. **Batch T — Welcome URL filter scope:** verify REG-FE-030 and coordinate with REG-FE-004/005, preserving unrelated query keys.
23. **Batch U — selection/date/a11y:** verify REG-FE-031/032/033 with component tests, clinic-zone boundary tests and axe/keyboard.
24. **Batch V — fail-closed queue read-model validation:** verify REG-FE-034 with malformed 200/valid empty responses and backend schema contract; mandatory frontend/backend contract gate before repair.
25. **Batch W — queue-manager latest selection:** verify REG-FE-035 with deferred A/B responses and component/queue resource tests, retain existing routing semantics.
26. **Additional batches:** one bounded fix PR per validated domain/root cause; never introduce a speculative blanket refactor or mix unrelated source fixes into this ledger PR.
27. **Validation:** relevant Vitest components/contracts, `tsc`/ESLint, affected Playwright flows with synthetic data, relevant queue contract tests, PR quality gates, `git diff --check`, and code review. Record **actual commands/results**; do not claim tests passed without execution.
28. **Closure:** update each ledger row with root cause, test evidence, fix PR/commit SHA, review outcome, and resolution status. Keep this audit PR as the index; merge it only when repository review and CI policy permit. Do not deploy as part of this audit.


## Cloud remediation execution plan — 2026-10-30 (planning only)

> **Authorization / scope:** cloud-hosted GitHub PR and CI workflow **plan**, not permission to deploy, migrate databases, execute against production, or merge. No fix branches/issues have been created by this plan. **All 35 candidate defects remain SOURCE-OBSERVED / REPRO-PENDING** until a controlled synthetic reproduction demonstrates them. The PR containing this plan remains documentation-only.

### Objective, invariants and execution model

Move the registrar's source-observed inventory to reproducible, reviewed, tested and safely integrated changes. The invariants of the clinic system are: backend as SSOT for queue owner/fairness/numbering, transitions, payments, user permissions and audit; **never** switch doctor ID and resource ID interchangeably; do not mutate a second patient's visit through numeric ID collision; no unverified success acknowledgements; no PHI or credentials in cloud logs or test fixtures.

Cloud agents operate on a *fresh* base fetched from `origin/main`, in an isolated clean worktree/branch, with GitHub PRs and GitHub Actions for validation. **One implementation PR cycle at a time**, per root [AGENTS.md](https://github.com/drsapaev/final/blob/main/AGENTS.md): finish required checks, review and merge/close/record the disposition, then begin the next. Independent agents may review contracts, develop synthetic test proposals and audit risks in parallel **read-only**, but must not make concurrent application PRs in this sequential clinic workflow. No deployment secrets or live patient data are needed for cloud repro.

**Gate:** For each candidate, read current `AGENTS.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/RULES.md`, `.ai-factory/DESCRIPTION.md`, relevant skill and canonical backend source. Choose `direct_execute` for a truly narrow, non-risky UI-only change; otherwise run the mandatory gate via **`ai/langgraph/scripts/run_agent_gate.ps1` from `ai/langgraph`**, including known root cause/scope. Stop if the gate fails or ownership is not established; do not run `agent_gate.py` directly or substitute a made-up approval. The docs-only audit update itself is a narrow `direct_execute` and does **not** run implementation gates.

### Stage 0 — prove, triage, and narrow (before implementing)

1. Pin a fresh `origin/main` SHA and current PR #3803 HEAD. Recheck each candidate against **current** source (the audit's frozen source was `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`; old findings are not automatically still open). Inspect existing branches/fix PRs and affected tests. Establish reachable caller paths; do not label dead legacy components as active faults.
2. Use fake timers, deferred network promises and **synthetic-only** rows with deliberate numeric ID collisions, mixed doctor/resource ownership, mixed payment/cancel outcomes and simulated lost responses. For each REG-FE ID, save a minimal failing test **before** altering production source. Record actual pre-fix failure, then post-fix pass. If no reproducible defect, record `NOT A BUG`, `DUPLICATE` or `NEEDS PRODUCT DECISION` with evidence instead of introducing a speculative fix.
3. Recalculate effective severity from **impact + reachability + reversibility**, not from the preliminary P2/P3. Confirm whether REG-FE-025 (mass cancel/refund), 015/017 (partial commands), 011 (partial persistence), 022/034/035 (truthfulness of worklist) warrant escalation. No P0/P1 is declared without evidence.
4. Snapshot the frontend API contracts: `/registrar/queues/today`, `/registrar/records/actions`, price overrides, edit-delta, resource routing, and `/queue/{specialist_id}/call-next`. Separate read-model tests from command mutation tests. Existing queued/doctor/resource compatibility should stay tested, not rewritten blindly.

### Candidate fix PRs (create **only after** its fail-first test)

| Candidate PR | Track | Finding IDs | Narrow purpose / ownership | Execution gate |
| --- | --- | --- | --- | --- |
| CR-01 | Safety | REG-FE-025 | Force-majeure owner-boundary and dry-run/POST parity | Mandatory: queue ownership + payments + RBAC |
| CR-02 | Safety | REG-FE-015, REG-FE-017 | Partial batch/cancellation result reconciliation | Mandatory if clinical/payment/queue command contract changes |
| CR-03 | Safety | REG-FE-014 | Truthful context-action acknowledgements | direct_execute UI-only if no domain/role/command change |
| CR-04 | Data | REG-FE-034 | Canonical queue API envelope validation | Mandatory: frontend/backend API contract |
| CR-05 | Data | REG-FE-035 | Latest doctor/day snapshot wins | Mandatory if queue ownership/selection semantics change; otherwise narrow UI boundary |
| CR-06 | Data | REG-FE-022 | Distinguish real allocated numbers from display ordinals | Mandatory: queue numbering/SSOT |
| CR-07 | Data | REG-FE-011 | Patient edit/visit-save transaction boundary | Mandatory: DB, clinical lifecycle, payments |
| CR-08 | Data | REG-FE-010 | Existing-patient profile update contract | Mandatory if profile/visit write contract changes |
| CR-09 | Safety | REG-FE-013 | PHI-safe diagnostic logging across registrar | Mandatory: privacy/security |
| CR-10 | Data | REG-FE-007, REG-FE-020, REG-FE-021 | Worklist refresh scheduling and cooldown correctness | direct_execute if UI-only; mandatory for API/rate-limit contract changes |
| CR-11 | Data | REG-FE-009 | Stable reschedule record identity | Mandatory if visit/queue identity or command semantics change |
| CR-12 | UX | REG-FE-012, REG-FE-016 | Wizard catalogue request freshness and visit forecast | direct_execute only if strictly UI-only |
| CR-13 | UX | REG-FE-018, REG-FE-019 | Post-save reconciliation and single success acknowledgement | mandatory if command outcome contract changes |
| CR-14 | UX | REG-FE-006, REG-FE-023, REG-FE-024, REG-FE-026 | Action availability, confirmation and menu routing | Mandatory if roles/actions/clinical policy change |
| CR-15 | UX | REG-FE-004, REG-FE-005, REG-FE-030 | Canonical status/date/URL navigation contract | Mandatory if queue status meaning changes; otherwise UI-only |
| CR-16 | UX | REG-FE-008, REG-FE-027, REG-FE-028, REG-FE-029 | Welcome counters and data-source feedback | Mandatory if changing backend owner/read model |
| CR-17 | Polish | REG-FE-031, REG-FE-032, REG-FE-033 | Unused selection, clinic-timezone display, accessibility | direct_execute if presentation-only |
| CR-18 | Polish | REG-FE-001, REG-FE-002, REG-FE-003 | Worklist row activation, search display and locale reactivity | direct_execute if presentation-only |

**Priority execution sequence:** Start with **Safety** and high-risk **Data**: `CR-01` (owner of a mass operation), `CR-02` (partial cancel/command truth), `CR-04` (malformed queue response), `CR-05` (doctor/day race), `CR-06` (real queue-number allocation), `CR-07` (patient/visit write boundary), `CR-09` (diagnostic PHI). The IDs are *candidate work packages, not existing GitHub PR numbers*. `CR-03/08/10/11` and other independent slices follow the highest verified risk. Finally fix UX/polish only after data/action contracts are stable. Work-package order can change with **newly confirmed** risk but never skip mandatory gates.

**Dependencies:** `CR-04` before `CR-16` (accurate empty/error-state display); `CR-02` before `CR-03/14` (command outcomes before success messaging); `CR-07` before `CR-08/13` if save workflows share the same write boundary; `CR-10` before `CR-13/16` when refresh behavior affects acknowledgements; `CR-15` before `CR-16/17` when date/filter scope affects displayed counts. `CR-01` may expose a new backend contract decision and must stop on mixed resource/doctor scope ambiguity, not guess. **Split any grouped package** if tests prove unrelated root causes, if the patch crosses two safety domains or if review scope becomes broad; never merge distinct root causes for a convenience bulk PR.

### Mandatory edge-case test matrix

| Area | Controlled synthetic scenario | Acceptance |
| --- | --- | --- |
| Force majeure (`025`) | doctor-owned, resource-owned, unknown and mixed-owner queue; stale view; dry-run followed by POST | Exact same authorized target identity in preview and mutation; unsupported scopes disabled; no unintended refund |
| Batch action/cancel (`014/015/017`) | mixed accepted/rejected/no-op records, response lost after commit, repeated click | Acknowledge only committed operations; return per-record outcomes; reconcile list; never blindly resubmit money/queue commands |
| Queue API (`022/034/035`) | malformed HTTP 200, valid empty `queues:[]`, missing linked DailyQueue, fallback ordinal, delayed doctor/date A vs B | Invalid data `error/stale`, true empty `empty`, real ticket only when allocated; B's selection wins |
| Patient/wizard (`009/010/011/012/016/018`) | two entities with same numeric ID; failed second command after first commit; stale catalogue day; failed refresh after committed save | Correct identity, explicit write boundaries, current catalogue, truthful visit count, no retry of committed create |
| Refresh (`007/008/020/021/035`) | HTTP 429 and Retry-After, overlapping A/B/C, modal open-close, WS update, unmount | No stale overwrite/false success, consistent cooldown and loading, no unhandled timers |
| Views/accessibility (`001/002/003/004/005/006/019/023/024/026/027–033`) | all-department grouping, zero-match vs zero-records, fetch error, role gating, locale switch, UTC-negative browser, keyboard navigation | Canonical statuses/action rights, preserved date/query scope, no ghost buttons/checks, correct clinic day and semantic names |
| Privacy (`013`) | nested synthetic patient names, phone numbers, IDs in thrown errors, logger primitives, telemetry breadcrumbs | Neither console nor telemetry leaks PHI; tests use no real identities |

### Single cloud-agent PR lifecycle

1. **Discover:** re-read current repo rules/SSOT sources, pin `origin/main` SHA, confirm finding still exists, and record selected `CR-XX`, candidate IDs, risk mode, allowed/denied files, known owner, test scope and stop condition.
2. **Gate and red test:** execute mandatory `run_agent_gate.ps1` if triggered and read its execution prompt. Create a **deterministic fail-first regression** against synthetic data, including a negative test and backend contract when the command/SSOT is involved. Report red test output; a test that passes when all actions are stubs is not sufficient.
3. **Minimal repair:** only after the failing proof, change the smallest canonical backend contract or React presentation/command-adapter branch necessary. Keep backend decision-making server-owned. Do not implement fallback patient/provider/queue guesses to conceal contract defects.
4. **Verify:** run focused Vitest/pytest, TypeScript strict check, relevant ESLint, API/OpenAPI and RBAC/integration checks for risky actions; run relevant Playwright synthetic registrar flows, and `git diff --check`. Run repository-required CI and security gates. Record **exact commands and results**; no fictitious green CI.
5. **Review:** open one appropriately labeled GitHub PR with pre-fix red/post-fix green evidence, test files, risk/gate logs, precise diff, rollout constraints and rollback procedure. Obtain independent code review, address findings, then merge only through normal branch protections. The existing #3803 remains an index, never a runtime-fix branch.
6. **Rebase/recheck and repeat:** begin the next PR from new `origin/main` only when the previous cycle has a recorded terminal outcome. Update the corresponding `REG-FE-XXX` ledger row with confirmed severity, reproduction, PR/commit links, validation and `CONFIRMED/RESOLVED/NOT A BUG/DUPLICATE`.

### Release and stop conditions

- **No automatic production deployment** from this plan. The plan covers a cloud development/PR/CI pipeline; a separate production change authorization, clean synced `main`, backup/restore evidence, deployment runbook and post-release monitoring are required. Test against isolated synthetic Postgres/test data only. A successful Vercel frontend build does **not** prove FastAPI/database/queue behaviors.
- **Stop on:** unknown/mixed queue ownership, doctor/resource ID ambiguity, unclear clinical/payment write semantics, uncertain result after lost response, failed mandatory gate, failing tests, missing required CI, missing safe rollback, leaked PII/credentials, or changes outside authorized app source scope. Do not retry a possibly committed payment/cancellation automatically.
- **Final completion evidence:** 35 original findings have grounded dispositions and no unresolved confirmed release-blocking issues; every fix has a failing-then-passing regression, required green CI, independent review and recorded merge; synthetic E2E covers booking → queue → call/start → payment/cancel → report and role boundaries; migration/backup/rollback rehearsals are documented where applicable. Reassess production readiness **separately** after these facts exist.

### Cloud agent launch brief (copy/paste when starting one cycle)

> Repository `drsapaev/final`. Read fresh `AGENTS.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/RULES.md`, relevant project skills and audit `docs/audits/2026-10-29-registrar-frontend-review-ledger.md`. Select **one** `CR-XX` package from the Cloud remediation execution plan and its `REG-FE-XXX` IDs. Pin current `origin/main`, inspect canonical backend owner/tests, establish reachability and run the mandatory project gate when triggered. **First write a synthetic failing test; if no bug, report NOT A BUG without changing runtime.** Make the smallest fix from the established root cause, keep backend SSOT, verify affected frontend/backend contracts and GitHub Actions, produce one scoped PR with exact evidence. Do not touch live patient data, credentials, deployments, production, main directly, or merge automatically. Stop on unsafe or unresolved domain decisions.

### Execution checkpoint — CR-01 / REG-FE-025 (2026-10-30)

- **Started:** [GitHub issue #3808 — CR-01 fail-first](https://github.com/drsapaev/final/issues/3808). This is a scoped **implementation ticket**, not a fix PR or completed change. The ticket records source baseline, owner identity ambiguities, negative tests, server preview/write parity and queue/payment rollback requirements.
- **Source verified read-only:** current main `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`; `useRegistrarRowActions.ts` opens specialist-scoped modal from `doctor_id || specialist_id`; canonical queue adapter carries owner kind/owner ID; `ForceMajeureModal` performs unbounded specialist preview and mass-transfer/refund requests; backend supports legitimate specialist-to-resource queue resolution but is not owner-typed at this API boundary. Existing test asserts the legacy fallback, not mixed/resource/unknown owner safety.
- **Mandatory gate: BLOCKED / NOT RUN.** The current connected-GitHub session can inspect and open issues, but its execution container has no checked-out repository, no PowerShell `pwsh`, and cannot resolve `github.com` for a clone. The mandated `ai/langgraph/scripts/run_agent_gate.ps1` cannot be executed here. Do not claim test, CI or gate evidence; **no application or test source edits permitted before gate**.
- **Cloud executor next action:** in an authorized cloud coding worktree from fresh `origin/main`, run the mandatory gate with confirmed scope, save its emitted prompt/evidence, first introduce a synthetic failing regression for doctor/resource/aggregate owner and preview-before-mass-action, then make the smallest safe fix, run affected tests/CI, and open exactly one Draft fix PR. Stop on unresolved owner-typed API decisions. **No merge or production deploy authorized.**
- **Tracking:** REG-FE-025 remains `SOURCE-OBSERVED / REPRO-PENDING`, severity provisional P2. No new issue IDs or finding statuses were changed.

### Execution checkpoint — CR-01 / REG-FE-025 (2026-10-30, cloud cycle 1 result)

- **Gate:** run before the first source edit from a fresh isolated worktree off `origin/main` `22b21a8b7c3c0b9b56f4e388c35e329a4321f768` via `ai/langgraph/scripts/run_agent_gate.ps1` (pwsh 7.5.2) with `--known-root-cause frontend/src/pages/registrar/useRegistrarRowActions.ts` + a 15-path reviewed scope → `narrow_override`; the plain gate's queue-fairness routing to backend queue files was recorded as a misroute and not followed (no router files changed). Scope expanded once (+ the Playwright spec) with the gate re-run before editing.
- **Fail-first:** 15 new-contract assertions RED on the untouched baseline — including the resource-owned row silently retargeting incidental doctor 3's whole queue, and a synchronous double submit firing the financial POST twice.
- **Fix:** frontend-only minimal change (canonical `queue_owner_kind`/`queue_owner_id` + row-day target; destructive actions gated by a successful non-empty dry-run bound to the same specialist + `target_date`; in-flight submit guard); backend contract untouched.
- **Evidence:** RED 15 → GREEN 40/40 (3 suites) + 216/216 affected modules, strict `tsc` 0, eslint 0 (pre-existing warnings only), `npm run build` ✓, Playwright synthetic scenario 2 passed, `git diff --check` clean; **Draft PR #3809** commit `4776cb279` — CI 40 check-runs, 22 success, 0 failures (incl. Frontend e2e with the new spec).
- **Tracking:** REG-FE-025 → `CONFIRMED / FIX-IN-REVIEW` (see findings index). Draft only — no merge/deploy from the cloud job; `RESOLVED` when #3809 is reviewed and merged.

## Change log

| Date | Ledger revision | Added / updated | Verification |
| --- | --- | --- | --- |
| 2026-10-29 | Initial | Three provisional source-observed findings; coverage, scope and remediation plan | GitHub source reads; remote PR/commit verified |
| 2026-10-29 | Review pass 2 | REG-FE-004–009: quick filters, URL date, Welcome confirmation, 429 handling, refresh notification, reschedule identity | Frontend hooks/views, backend read-model helpers and existing tests inspected; runtime tests not executed |
| 2026-10-30 | Review pass 3 | REG-FE-010–013: existing patient edits, partial profile/queue save, stale wizard catalogue, development PII logging | Wizard UI/handlers, API mappers, privacy logger, wizard tests inspected; no runtime tests executed; new main source SHA `22b21a8b7c3c0b9b56f4e388c35e329a4321f768` |
| 2026-10-30 | Review pass 4 | REG-FE-014–016: context-action false success, partial batch reconcile, cart visit-count display; pinned doctor/route guard inspected | Backend per-record command path and relevant frontend hooks/tests inspected; no runtime tests executed |
| 2026-10-30 | Five-group protocol / Group 1 | REG-FE-017–019: cancellation acknowledgement, post-wizard retry, duplicate toasts. Ordered remaining Groups 2–5 per user request | Named three files and necessary callers/tests inspected at main SHA `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`; no runtime tests |
| 2026-10-30 | Five-group protocol / Group 2 | REG-FE-020–022: stale request in-flight cleanup, modal interval snapshot, apparent queue number without linked DailyQueue; preexisting REG-FE-002/005/007 not duplicated | Named three files, backend DTO/ownership/number resolver and matching unit tests inspected at main SHA `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`; no runtime tests |
| 2026-10-30 | Five-group protocol / Group 3 | REG-FE-023–026: dead schedule-next action, missing grouped action visibility, force-majeure target mismatch, hidden context reschedule; expanded existing REG-FE-013 evidence without duplicate | Two primary action hooks, context menu, server action/owner contracts, force-majeure and focused tests inspected at main SHA `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`; no runtime tests |
| 2026-10-30 | Five-group protocol / Group 4 | REG-FE-027–033: Welcome summary, filtered/no-data/error semantics, URL query preservation, orphaned selection, clinic date formatting and unlabeled all-departments tabpanel. Existing 001/004/005/006/008/013 not duplicated | Three views, queue manager, adapters, table, navigation and focused tests inspected at main `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`; no runtime tests |
| 2026-10-30 | Five-group protocol / Group 5; source inventory complete | REG-FE-034–035: malformed canonical queue API response silently treated as empty, and older queue-manager snapshot supersedes current doctor/day. Verified date/catalog, price route, auth/CSRF replay and backend resource call routing; dormant demo selector excluded as unproven live risk | API clients, mappers, selector hooks, backend endpoints/domain and focused frontend/backend test sources inspected at main `22b21a8b7c3c0b9b56f4e388c35e329a4321f768`; no runtime/automated tests |
| 2026-10-30 | Cloud remediation plan (documentation only) | Added Stage 0 triage, 18 candidate small-PR packages with **exact 35-ID coverage**, cloud agent workflow, risk gate, test matrix, dependencies and release stop conditions. No app fixes or deployment authorized | Current #3803 draft and audit/main SHA inspected; plan text/index coverage checked; no source, runtime tests or CI executed |
| 2026-10-30 | CR-01 start / gate blocker checkpoint | Created GitHub issue #3808 with precise fail-first/owner/preview requirements; source rechecked. Mandatory PowerShell gate cannot run in this no-checkout/no-pwsh execution container | No code/test edits, no gate/test/CI execution; issue confirmed in GitHub. Status remains SOURCE-OBSERVED / REPRO-PENDING |
| 2026-10-30 | CR-01 cloud cycle 1 | REG-FE-025 → CONFIRMED / FIX-IN-REVIEW: mandatory gate run (narrow_override), fail-first RED 15 → GREEN, Draft PR #3809 opened with CI green (22 success / 0 fail) | Worktree gate payload + vitest/tsc/eslint/build/Playwright logs; PR #3809 checks on commit 4776cb279 |
| 2026-11-01 | Comprehensive remaining registrar frontend directory source sweep | REG-FE-036–049 provisional; inspected additional hooks, reschedule, actual patient ID hydrating, queue manager state, inline permissions, ModernStatistics, CSV, dialog focus, CSS, stories and named unit-test case inventory across six dirs | GitHub source reads at fresh main a770ce3373b6e4b69f54b51723e1f2775dac4088; no browser/Vitest/pytest/Playwright/agent gate or production action. Existing REG-FE-025 recent-main safeguards rechecked source only. |

| 2026-11-01 | Follow-up triage + implementation issues | Source-to-backend contracts strengthened for REG-FE-036 and REG-FE-040/041; opened implementation tracking issues #3819 and #3820 with synthetic red-first tests, and checked REG-FE-038/039/043 | GitHub source-only; no tests, mandatory gate, runtime edits, merge, deploy, or live patient data |

| 2026-11-01 | Focused table files audit | Added REG-FE-050–055: string/date sorting, filter/page false-empty, canonical status mislabel, nested services search, context menu keyboard/focus, unstable row keys. Expanded existing REG-FE-004/031 without duplicating | Pinned GitHub main source, 11 table files and parent/backend contracts; no new runtime tests, gate, source edits or deploy |

## End-of-review acceptance criteria

- Every finding has a unique stable ID and a final disposition: `CONFIRMED`, `NOT A BUG`, `DUPLICATE`, or `RESOLVED`.
- Confirmed defects have focused regression tests; no test exists merely to silence a failure.
- Changes preserve backend queue fairness, identities, clinical/payment ownership, RBAC, and privacy guardrails.
- Fix PRs are reviewed, all required CI is green, and the final ledger links to those PRs/commits.
- This document by itself is **not evidence** that the registrar workflow is safe or fully audited.
