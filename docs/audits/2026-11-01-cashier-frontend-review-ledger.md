# Cashier frontend audit ledger — 2026-11-01

> **Status:** SOURCE REVIEW COMPLETE (BOUNDED) / read-only audit. No execution proof or production-readiness or financial-safety certification.
>
> **Baseline:** `origin/main` at `f308ed97e7f640a33e2bb255e23aaa109e69110a` (GitHub code search + pinned file reads). All findings provisional (`SOURCE-OBSERVED / REPRO-PENDING`); no Vitest, Playwright, pytest or CI was run. No application code, tests, backend, payments, database, secrets, or production touched.
>
> **Scope:** Only the cashier route and components that its active import graph reaches; the inventory lists directly mounted files and explicitly marked shared dependencies. This audit is **not** a statement that all frontend files or every indirect helper have been line-reviewed.

## Execution boundary

- Mode: **`direct_execute` documentation-only inventory and inspection. No application behavior is edited**. Any later fix affecting payments, refunds, cash settlement, RBAC, deposits, idempotency, API contracts, or production needs the repository's **mandatory** `ai/langgraph/scripts/run_agent_gate.ps1` before source edits (read `AGENTS.md` and the emitted execution prompt; do not substitute bare Python).
- The backend is the SSOT for amounts, payment/refund state, allocation, available actions, role grants and transaction/receipt identity. Do not infer permission from CSS or local display status. Never publish actual PHI/payment instruments, use only fabricated fixtures.
- This ledger is independently tracked from [registrar audit #3803](https://github.com/drsapaev/final/pull/3803), which completed five **bounded source groups**, not exhaustive review of all connected frontend files. Do not conflate cashier defects with registrar hypotheses.
- Every candidate needs a fail-first focused regression, minimal independently reviewed fix PR, exact test execution evidence, and closing status. No automatic merge/deploy.

## Active source inventory (GitHub directory listings + import reads)

**Route:** `frontend/src/pages/CashierPanel.tsx` (346 lines): directly imports/calls the cashier hooks and renders the pending/history/refunds tabs.

**Page-local files, all enumerated (nine):**

- `frontend/src/pages/cashier/cashierPaymentContracts.ts`
- `frontend/src/pages/cashier/cashierPaymentRows.ts`
- `frontend/src/pages/cashier/useCashierActions.ts`
- `frontend/src/pages/cashier/useCashierDialogs.ts`
- `frontend/src/pages/cashier/useCashierFilters.ts`
- `frontend/src/pages/cashier/useCashierSearch.ts`
- `frontend/src/pages/cashier/useCashierSessionWarning.ts`
- `frontend/src/pages/cashier/useCashierSort.ts`
- `frontend/src/pages/cashier/useCashierWorklistData.ts`

**Presentation files, all enumerated (six):** `views/CashierDialogsLayer.tsx`, `CashierFiltersCard.tsx`, `CashierHistoryTable.tsx`, `CashierPendingTable.tsx`, `CashierServiceBadges.tsx`, `CashierStatsCard.tsx` under `frontend/src/pages/cashier/`.

**Cashier refund component files, excluding CSS and tests (four):** `frontend/src/components/cashier/RefundRequestsTable.tsx`, `refundRequestsColumns.tsx`, `refundRequestsContracts.ts`, `useRefundRequests.ts`. CSS: `RefundRequestsTable.css` and `frontend/src/pages/cashier.css` are within UI review scope.

**Shared, referenced components/hooks to review:** `frontend/src/hooks/usePayments.ts`, `frontend/src/components/payment/CashPaymentModal.tsx`, `frontend/src/components/payment/PaymentWidget.tsx`, `frontend/src/components/ui/macos/MacOSTab.tsx`, `frontend/src/components/common/ConfirmDialog.tsx`, `frontend/src/api/client.ts`, receipt/print helpers and relevant auth/route code. These are scoped **dependencies**, not all fully reviewed yet.

**Located existing tests:** `frontend/src/pages/cashier/__tests__/{cashierPaymentContracts,cashierPaymentRows,useCashierActions,useCashierDialogs,useCashierSort,useCashierWorklistData}.test.ts` (6); `frontend/src/components/cashier/__tests__/{RefundRequestsTable.contract.test.tsx,useRefundRequests.test.ts}` (2); panel contract and i18n tests under `pages/__tests__`; backend `app/api/v1/endpoints/cashier/_payments.py` and related endpoints, cashier service and tests to be reviewed in Group 5. File discovery is not proof of test success.

## Review protocol and progress

1. **Group 1 — composition, data reads, filters and tables: BOUNDED SOURCE REVIEW DONE (2026-11-01).** Inspected all core listed page hooks, data filters/search/sort and active table views, source tests and backend search contract. CSH-FE-001–006 are provisional.
2. **Group 2 — financial commands and payment lifecycle: CORE SOURCE REVIEW DONE (2026-11-01), provider contracts deferred to Group 5.** Inspected cashier actions, contracts, cash/online widgets, usePayments mutation calls, backend direct/grouped/confirm, PaymentInvariantService and relevant existing tests. CSH-FE-007–010 are provisional.
3. **Group 3 — refund requests, deposits and permissions: BOUNDED SOURCE REVIEW DONE (2026-11-01), integration tests pending.** Reviewed four refund components, source tests, refund/deposit backend, canonical routes, CSRF/auth, available_actions and deposit ledger locking. CSH-FE-011–018 remain provisional; cash refund status does not prove external transfer.
4. **Group 4 — dialogs, printing, filtering and accessibility: BOUNDED SOURCE REVIEW DONE (2026-11-01), browser/test proof pending.** Read all cashier dialogs, session warning, print/receipt construction + backend PDF endpoint, hotkeys, sortable headers, refund validation and dates. CSH-FE-019–027 remain provisional. Existing test source inspected, not executed.
5. **Group 5 — API/backend contracts and regression coverage: BOUNDED SOURCE REVIEW DONE (2026-11-01); targeted runtime tests NOT RUN.** Checked cashier API/SSOT/payment-provider initiation and status routes, CSRF/RBAC, CSV/PDF, partial refund and the source-test inventory. CSH-FE-028–035 added. Verified CI metadata: Unified CI successful on prior audit head; PR Review Quality Gate failed on missing mandatory PR-body sections, not code tests.

## Findings index

| ID | Provisional priority | Scope | Source-derived observation | Evidence status | Planned test |
| --- | --- | --- | --- | --- | --- |
| CSH-FE-001 | P2 | Pending/history read errors | Failed list request clears rows, no distinct failure/stale state; UI shows operational empty state | SOURCE-OBSERVED / REPRO-PENDING | failed refresh vs real empty response |
| CSH-FE-002 | P2 | Async query identity | Overlapping date/search/page requests can overwrite newer result; shared pending/history loading can clear prematurely | SOURCE-OBSERVED / REPRO-PENDING | deferred A/B out-of-order |
| CSH-FE-003 | P3 | Pending badge count | Tab badge uses current-page `appointments.length` instead of server `pendingTotalItems` | SOURCE-OBSERVED / REPRO-PENDING | 21 rows / page-size 20 |
| CSH-FE-004 | P2 | Independent payment grouping | Same-minute payments summed into one row but status, method, permissions and actions belong to only the first payment | SOURCE-OBSERVED / REPRO-PENDING | two same-minute payment IDs with mixed statuses and actions |
| CSH-FE-005 | P3 | History sort order | Localized display dates are compared as strings and sorting affects only the already loaded server page | SOURCE-OBSERVED / REPRO-PENDING | 31 Jan vs 1 Feb and two server pages |
| CSH-FE-006 | P2 | Cashier patientId deep link | Query initializes as patient:ID but lookup guard skips resolution and backend search only matches names | SOURCE-OBSERVED / REPRO-PENDING | mount URL ?patientId=42 and mock patient lookup |
| CSH-FE-007 | P2 | Partial-payment default | Cash dialog defaults to full total_amount instead of remaining_amount; single-visit backend allows excess as an advance | SOURCE-OBSERVED / REPRO-PENDING | total=100 paid=70 remaining=30 |
| CSH-FE-008 | P2 | Cash double submit | Modal async submit has no single-flight guard and its submit button remains enabled during POST | SOURCE-OBSERVED / REPRO-PENDING | two fast submits with deferred payment API |
| CSH-FE-009 | P2 | Cash tender field | Blank received amount becomes zero and bypasses insufficient-cash check while a positive payment amount can be submitted | SOURCE-OBSERVED / REPRO-PENDING | cash due>0, received blank/0/less/equal/more |
| CSH-FE-010 | P2 | Local smoke online settlement | DEV or localhost initializes provider payment then invokes real cashier manual confirmation before provider settlement | SOURCE-OBSERVED / REPRO-PENDING | isolated production build on localhost versus dev test-only backend |
| CSH-FE-011 | P2 | Refund API URL | Origin-relative /force-majeure path misses /api/v1 and configured API origin | SOURCE-OBSERVED / REPRO-PENDING | dev proxy /api-only, separate API host, 404 |
| CSH-FE-012 | P2 | Refund POST CSRF/refresh | Raw POST lacks X-CSRF-Token and bypasses shared token refresh handling | SOURCE-OBSERVED / REPRO-PENDING | CSRF enabled, 403 missing header, expired 401 |
| CSH-FE-013 | P2 | Global refresh | Toolbar refresh reloads stats/pending/history but not mounted refund request table | SOURCE-OBSERVED / REPRO-PENDING | mount RefundRequestsTable then click global Refresh |
| CSH-FE-014 | P2 | Refund list completeness | Backend defaults to 50 requests while UI provides no offset, pagination or total badge | SOURCE-OBSERVED / REPRO-PENDING | 51 and 201 refund requests, later pending item |
| CSH-FE-015 | P2 | Refund fetch freshness | Old filter response can overwrite newly selected refund list and its loading flag | SOURCE-OBSERVED / REPRO-PENDING | deferred pending A and approved B, reverse responses |
| CSH-FE-016 | P2 | Refund completion truthfulness | UI Выплатить triggers status-only complete, without verified payout evidence | SOURCE-OBSERVED / REPRO-PENDING | approved bank_transfer, no external transfer reference |
| CSH-FE-017 | P3 | Refund error and empty UX | Failed initial fetch presents both AppError and genuine no-request empty state | SOURCE-OBSERVED / REPRO-PENDING | initial request fails versus HTTP 200 empty list |
| CSH-FE-018 | P3 | Refund duplicate click | State-only processingId may allow two actions before disabled controls rerender | SOURCE-OBSERVED / REPRO-PENDING | two fast process invocations before first response |
| CSH-FE-019 | P2 | Receipt source of truth | Browser receipt prints view-model rows without authoritative server receipt; backend permits print for all statuses | SOURCE-OBSERVED / REPRO-PENDING | stale row vs server-paid/refunded status and receipt PDF |
| CSH-FE-020 | P2 | Receipt line reconciliation | When several service names exist, the receipt builder assigns entire payment total to each line | SOURCE-OBSERVED / REPRO-PENDING | two named services, total 100: line sum must equal total |
| CSH-FE-021 | P3 | Print fallback notification | Successful backend PDF download still causes misleading 'print dialog failed' warning | SOURCE-OBSERVED / REPRO-PENDING | popup blocked then GET PDF succeeds |
| CSH-FE-022 | P2 | Session extension semantics | 'Extend session' action only closes warning and says extension started; never refreshes access token | SOURCE-OBSERVED / REPRO-PENDING | expiry within 30 sec, click Extend, JWT exp unchanged |
| CSH-FE-023 | P2 | Session expiry during mutation | Expired-token callback forces /login even if a payment/refund request has not completed | SOURCE-OBSERVED / REPRO-PENDING | deferred payment POST and expired token event |
| CSH-FE-024 | P3 | Refund dialog validation | Min/max DOM hints are not enforced by click handler; parseFloat accepts malformed/truncated input and original total is the max | SOURCE-OBSERVED / REPRO-PENDING | refund 100 already 70; blank, -5, 40, 2.5e2, text |
| CSH-FE-025 | P3 | Sortable headers accessibility | Cashier history clickable th has no keyboard focus/Enter/Space semantics or aria-sort | SOURCE-OBSERVED / REPRO-PENDING | keyboard tab, Enter/Space and screen-reader sort announcement |
| CSH-FE-026 | P3 | Global hotkeys in dialogs | Ctrl+F/R/E and F5 hijack browser operations even while input/textarea is focused | SOURCE-OBSERVED / REPRO-PENDING | focused refund reason / cash amount, Ctrl+E or Ctrl+F |
| CSH-FE-027 | P3 | Hourly analytics date scope | Range-mode analytics uses stale hidden single-day selectedDate instead of visible date range | SOURCE-OBSERVED / REPRO-PENDING | select range Sept1–5, click Hourly statistics |
| CSH-FE-028 | P2 | Refund-aware outstanding balance | Pending list, stats and grouped allocation count gross paid amounts after partial refunds; canonical invariant uses net settled amount | SOURCE-OBSERVED / REPRO-PENDING | single and grouped visit partial refund, pending due net vs gross |
| CSH-FE-029 | P2 | Online payment automatic polling | Polling interval closes over first-render paymentData=null, so repeated checks may never reach canonical status GET | SOURCE-OBSERVED / REPRO-PENDING | provider init returns payment_id; fake clock 5/10 sec; expect GET /payments/id |
| CSH-FE-030 | P2 | Provider load effect stability | Translation t identity changes each render, causing loadProviders useCallback and useEffect to fetch again after state updates | SOURCE-OBSERVED / REPRO-PENDING | mock providers 200, render PaymentWidget; GET count stable across rerenders |
| CSH-FE-031 | P2 | Payment poll timeout semantics | Five-minute observation limit sets backend payment UI status to failed even without provider failure | SOURCE-OBSERVED / REPRO-PENDING | provider pending for 60 polls, then provider paid after timeout |
| CSH-FE-032 | P2 | CSV export completeness | Cashier export silently limits to 10,000 newest payments with no truncation metadata | SOURCE-OBSERVED / REPRO-PENDING | 10001 matching synthetic records, compare CSV row count to source count |
| CSH-FE-033 | P3 | CSV refund status | CSV maps refunded statuses to pending 'Ожидает' instead of returned | SOURCE-OBSERVED / REPRO-PENDING | paid, refunded, cancelled, processing distinct CSV rows |
| CSH-FE-034 | P2 | Spreadsheet injection on export | Cashier CSV writes patient names and free-text notes without spreadsheet formula neutralization | SOURCE-OBSERVED / REPRO-PENDING | untrusted name/note starting =,+,-,@, tab and safe text |
| CSH-FE-035 | P2 | Successful HTTP envelope validation | usePayments GET accepts malformed 200 JSON as success/empty with unvalidated pagination metadata | SOURCE-OBSERVED / REPRO-PENDING | HTTP 200 with {message:'error'}, string, missing items, invalid total |
| CSH-FE-036 | Undecided | Stats totals gross vs net-of-refunds | `/cashier/stats` `total_amount`/`cash_amount`/`card_amount` still sum original payment amounts while `pending_amount` is now net-of-refunds; owner decision required before classification as an error | SOURCE-OBSERVED / DECISION-PENDING | paid 100 + partial refund 30: totals show 100, pending debt uses 70 |

### CSH-FE-001 — HTTP error is shown as a genuinely empty cashier selection (P2 candidate)

**Evidence:** [useCashierWorklistData.ts L137–L173](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/frontend/src/pages/cashier/useCashierWorklistData.ts#L137-L173) on `getPendingPayments` unsuccessful result or rejection executes `setAppointments([])`; [L175–L216](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/frontend/src/pages/cashier/useCashierWorklistData.ts#L175-L216) likewise sets `setPayments([])` for history. There is no read-error state exported to the panel. [usePayments.ts L83–L132](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/frontend/src/hooks/usePayments.ts#L83-L132) returns a `success:false` result on a failed pending request, rather than throwing. [CashierPendingTable.tsx L201–L214](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/frontend/src/pages/cashier/views/CashierPendingTable.tsx#L201-L214) renders the empty payment queue state for the empty array; [CashierHistoryTable.tsx L206–L219](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/frontend/src/pages/cashier/views/CashierHistoryTable.tsx#L206-L219) similarly shows the empty-history state. [Existing tests L147–L166](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/frontend/src/pages/cashier/__tests__/useCashierWorklistData.test.ts#L147-L166) deliberately pin clearing rows on failure.

**Potential impact:** when a refresh fails after valid rows were loaded, those rows disappear, creating the appearance of zero pending payments/zero history while the server was unavailable. The state is not reported as a financial zero by the backend; this is a misleading UI presentation. Do not claim actual balances/payments were changed.

**Fail-first test:** load 2 synthetic pending and 1 history row; issue a second refresh that rejects/returns `success:false`; assert the page retains previously loaded values as clearly **stale**, displays an error/retry action and never shows "no pending payments" or "empty history" as if confirmed by server. On a successful `items:[]`, it must show the genuine empty state. Consider initial failure separately. Backend remains SSOT.

**Fix direction:** model `loading/success/error/stale` separately per section in hook; present error/retry in views; keep previous successful samples on refresh failure, and clear only on a successfully validated empty response. Do not invent local receipt/payment state.

### CSH-FE-002 — Old cashier read response can overwrite a newer date/search/page selection (P2 candidate)

**Evidence:** [useCashierWorklistData.ts L115–L216](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/frontend/src/pages/cashier/useCashierWorklistData.ts#L115-L216) starts three independent async effects (stats/pending/history); their state writes `setStats`, `setAppointments`, `setPayments`, pagination and loading are unconditional after `await`. No cleanup cancellation, AbortController or monotonically increasing request identity protects the selected date/search/page. Inputs trigger new effects, and responses may return out of order. The tests [useCashierWorklistData.test.ts L58–L246](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/frontend/src/pages/cashier/__tests__/useCashierWorklistData.test.ts#L58-L246) cover mapping, pagination/filter params and intentional clear-on-fail, not out-of-order A/B promises.

**Potential impact:** user changes date from A to B; B response resolves first, then A resolves and overwrites visible rows/stats while B remains selected. Financial UI can display records for the wrong date/filter, but there is no proof of any backend mutation. Shared `loading` booleans may be set false by an older request while a newer one is in flight.

**Fail-first test:** for each of stats, pending, and history, use synthetic deferred A/B responses, change date/status/search/page, resolve B then A, and assert B remains visible and loading remains true until B settles when A resolves earlier. Cover unmount and failure of superseded request.

**Fix direction:** guard each dataset by the current request epoch/query identity, or cancel obsolete transport; only the latest result may update its own list/metadata/loading state. Keep server-side paging and existing API scopes.

### CSH-FE-003 — Pending tab badge reports only current page size, not total pending rows (P3 candidate)

**Evidence:** [CashierPanel.tsx L218–L230](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/frontend/src/pages/CashierPanel.tsx#L218-L230) sets the pending-tab badge to `appointments.length`, yet the same panel receives `pendingTotalItems` ([L100–L110](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/frontend/src/pages/CashierPanel.tsx#L100-L110)) and passes it to the table [L258–L265](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/frontend/src/pages/CashierPanel.tsx#L258-L265). The hook requests `size:20` and stores server `pagination.total` in [useCashierWorklistData.ts L145–L160](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/frontend/src/pages/cashier/useCashierWorklistData.ts#L145-L160); the cashier pending endpoint has canonical total/page/size counts after grouping ([backend cashier/_payments.py L36–L53](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/backend/app/api/v1/endpoints/cashier/_payments.py#L36-L53)).

**Potential impact:** 37 pending patient rows with page size 20 show a tab badge of 20; the total count displayed in pagination may disagree. This is presentation-only and not a payment loss.

**Fail-first test:** with a synthetic backend response `{items:[20 rows],total:37,page:1,size:20,pages:2}`, expect pending badge `37`, then switch to page 2 and expect it to remain `37`; after a reload, update from the real server total. **Fix:** use `pendingTotalItems` for the tab badge, keeping no badge for zero if desired.

### CSH-FE-004 — Merged history row hides distinct command targets (P2 candidate)

**Source evidence:** [cashierPaymentRows.ts lines 24–74](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/cashierPaymentRows.ts#L24-L74) combines payment IDs by patient and displayed minute and sums their amounts; its first item retains status/method/available_actions. [CashierHistoryTable.tsx lines 117–199](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/views/CashierHistoryTable.tsx#L117-L199) displays the aggregate and calls confirmPayment(row.id), while the backend [_payments.py lines 319–375](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L319-L375) returns individual Payment IDs and per-payment actions. Existing [cashierPaymentRows.test.ts lines 35–47](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/__tests__/cashierPaymentRows.test.ts#L35-L47) requires same-minute grouping but never checks mixed permissions.

**Potential impact:** A displayed aggregate amount/status may not match the single record being confirmed, refunded or cancelled. Wrong transfer has NOT been reproduced.

**Required fail-first test / safe fix:** Fail-first with two payments (100 and 50) in the same minute, mixed statuses/methods/actions and unknown patient_id=0. Require a distinct action target per row, or separate read-only aggregate from per-payment actions; backend remains SSOT.

### CSH-FE-005 — Date and amount sort do not represent global chronology (P3 candidate)

**Source evidence:** [cashierPaymentRows.ts lines 82–103](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/cashierPaymentRows.ts#L82-L103) compares concatenated display date/time strings; [dateUtils.ts lines 58–66](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/utils/dateUtils.ts#L58-L66) formats localized day/month/year. Existing [cashierPaymentRows.test.ts lines 118–136](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/__tests__/cashierPaymentRows.test.ts#L118-L136) instead injects ISO dates. Backend [_payments.py lines 319–325](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L319-L325) already paginates before React sorts the loaded subset.

**Potential impact:** Chronology can reverse at calendar boundaries, and amount/patient sort only changes rows of the current page.

**Required fail-first test / safe fix:** Fail-first 31.01.2026 versus 01.02.2026 and amounts split across pages; compare canonical timestamps, preserve localized display, label page-local sort or implement verified backend sorting.

### CSH-FE-006 — patientId deep link cannot resolve its initial search (P2 candidate)

**Source evidence:** [useCashierSearch.ts lines 29–61](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/useCashierSearch.ts#L29-L61) initializes query with patient:42, then only looks up patient details when the query does NOT include patient:42; initial lookup therefore does not run. Both pending [_payments.py lines 76–85](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L76-L85) and history [_payments.py lines 298–309](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L298-L309) use patient-name ilike, not patient:ID syntax.

**Potential impact:** A valid patient deep link can appear to have no pending/history rows; a later async lookup can also race with URL navigation.

**Required fail-first test / safe fix:** Fail-first react-router deep link plus synthetic patient and out-of-order A/B navigations; resolve exact patient ID with backend-supported search or explicit guarded patient-name resolution, never silently claim empty.

### CSH-FE-007 — Prefill and pending row can overstate the remaining debt (P2 candidate)

**Source evidence:** [CashPaymentModal.tsx lines 53–73](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/payment/CashPaymentModal.tsx#L53-L73) chooses total_amount before remaining_amount, as does pending table [CashierPendingTable.tsx lines 131–136](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/views/CashierPendingTable.tsx#L131-L136). Backend pending DTO [_payments.py lines 226–252](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L226-L252) provides total, paid and remaining. Single-visit backend [_payments.py lines 694–739](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L694-L739) expressly accepts overpayment while debt remains; backend PaymentInvariantService documents the advance policy, whereas grouped payment route [_payments.py lines 450–463](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L450-L463) rejects excess.

**Potential impact:** A partially paid visit can default to charging its entire original price and recording the difference as advance. No real overcharge observed; prioritize fail-first due to financial impact.

**Required fail-first test / safe fix:** Render synthetic total=100 paid=70 remaining=30; check pending amount, modal due, submitted default and cash change =30. Change default to server remaining balance; require an explicit advance flow for deliberate overpay, and mandatory payment gate.

### CSH-FE-008 — Cash payment window allows concurrent submissions (P2 candidate)

**Source evidence:** [CashPaymentModal.tsx lines 89–106](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/payment/CashPaymentModal.tsx#L89-L106) calls onProcessPayment without awaiting/guard, and [CashPaymentModal.tsx lines 258–265](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/payment/CashPaymentModal.tsx#L258-L265) has an always-enabled submit. The parent [useCashierActions.ts lines 178–216](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/useCashierActions.ts#L178-L216) closes only after POST resolves and does not hold a synchronous single-flight guard for that modal. Backend row locking reduces duplicates but does not prove idempotency of two intentional-looking partial payments.

**Potential impact:** Two quick clicks can send two payment creation commands; do not claim they both committed without a deterministic backend test.

**Required fail-first test / safe fix:** Fail-first deferred promise and two synchronous submits: exactly one command, disabled in-flight button and recovery on failure. Also verify backend reconciliation/idempotency and do not rely on UI alone.

### CSH-FE-009 — Cash paid command does not require recorded tender (P2 candidate)

**Source evidence:** [CashPaymentModal.tsx lines 75–106](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/payment/CashPaymentModal.tsx#L75-L106) computes numericReceived=0 for blank input and treats <=0 as not insufficient, then sends declared amount with received_amount=0; received field [CashPaymentModal.tsx lines 188–201](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/payment/CashPaymentModal.tsx#L188-L201) is optional. Parent [useCashierActions.ts lines 191–203](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/useCashierActions.ts#L191-L203) forwards amount/method/note, not received_amount.

**Potential impact:** If the clinic policy requires actual cash collected before marking paid, the UI does not enforce it. A blank entry does not prove zero physical cash. Product-policy decision required.

**Required fail-first test / safe fix:** Synthetic cash due=100, received blank/0/50/100/150; test the intended tender requirement and change. If received is intentionally optional, record NEEDS PRODUCT DECISION rather than mandate new backend behavior.

### CSH-FE-010 — Local smoke auto-confirm can use the real paid state transition (P2 candidate)

**Source evidence:** [PaymentWidget.tsx lines 89–92](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/payment/PaymentWidget.tsx#L89-L92) enables local smoke by DEV or localhost hostname; [PaymentWidget.tsx lines 264–303](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/payment/PaymentWidget.tsx#L264-L303) calls cashier manual confirm on the returned payment ID. Backend [_payments.py lines 1023–1113](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L1023-L1113) is an Admin/Cashier endpoint that sets payment status paid through BillingService.

**Potential impact:** A locally served real clinic application could mark an online payment paid without a provider webhook. No evidence that deployed production exposes the local branch, or that unprivileged users can call confirm.

**Required fail-first test / safe fix:** Verify real/staging build topology and isolated synthetic provider flows, then require an explicit test-only backend guard. Mandatory payment/security gate; avoid indiscriminate removal of approved smoke tests.

### Audit checkpoint — Group 1 completed; Group 2 core reviewed (2026-11-01)

- **Fresh main:** a770ce3373b6e4b69f54b51723e1f2775dac4088 (one commit ahead of initial audit baseline f308ed97e7f640a33e2bb255e23aaa109e69110a; GitHub compare showed no inspected cashier/React frontend file changed).
- **Group 1 bounded source DONE:** CashierPanel.tsx, cashierPaymentRows.ts, useCashierSearch.ts, useCashierFilters.ts, useCashierSort.ts, useCashierWorklistData.ts, CashierFiltersCard.tsx, CashierStatsCard.tsx, CashierServiceBadges.tsx, CashierPendingTable.tsx, CashierHistoryTable.tsx and matching source-level unit tests, plus backend pending/history search. CSH-FE-001 through 006 are provisional.
- **Group 2 core SOURCE REVIEW DONE, external provider contract deferred to Group 5:** useCashierActions.ts, cashierPaymentContracts.ts, CashPaymentModal.tsx, PaymentWidget.tsx, usePayments.ts mutation calls and CashierDialogsLayer command wiring; backend cashier direct/grouped/confirm and PaymentInvariantService; source tests useCashierActions.test.ts and cashierPaymentContracts.test.ts. CSH-FE-007 through 010 are provisional. Backend owns grouped allocation/one DB commit, direct payment Visit locking and payment action availability. Do not mistake those code properties for end-to-end finance verification.
- **Deferred:** Group 3 refund requests/deposits, Group 4 receipt/dialog/accessibility details, Group 5 provider status contracts, RBAC, network retry, idempotency and actual CI evidence. No runtime or automated tests executed. Payment source fixes require AGENTS.md mandatory gate.

### CSH-FE-011 — Incorrect origin-relative refund endpoint (P2 candidate)

**Source evidence:** The refund hook [useRefundRequests.ts:30-46](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/cashier/useRefundRequests.ts#L30-L46) fetches /force-majeure/refund-requests. Backend mounts /force-majeure inside an API router ([api.py:571-576](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/api.py#L571-L576)) with outer /api/v1 prefix ([main.py:424-427](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/main.py#L424-L427)). Vite proxies only /api ([vite.config.ts:119-132](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/vite.config.ts#L119-L132)) and runtime accepts a separate origin ([runtime.ts:99-116](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/api/runtime.ts#L99-L116)).

**Impact and qualification:** Refunds may read from the static SPA origin or a wrong path. The production reverse proxy has not been tested.

**Fail-first / safe direction:** Synthetic Vite/prod split-origin test: assert the canonical API URL and a real list; do not invent a root alias.

### CSH-FE-012 — Refund commands bypass shared CSRF and reauthentication (P2 candidate)

**Source evidence:** The POST [useRefundRequests.ts:66-81](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/cashier/useRefundRequests.ts#L66-L81) sends only Bearer and Content-Type; the shared Axios client adds CSRF and refresh handling ([client.ts:329-396](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/api/client.ts#L329-L396)). Backend middleware rejects state-changing requests without X-CSRF-Token and cookie ([csrf_middleware.py:184-245](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/middleware/csrf_middleware.py#L184-L245)); production enables CSRF by default ([main.py:361-369](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/main.py#L361-L369)).

**Impact and qualification:** Commands may fail 403 after correcting the path; expired auth receives no shared recovery. This is a contract failure, not a proven unauthorized payment.

**Fail-first / safe direction:** Run 401/403 integration with synthetic auth and middleware; use shared client, avoid blind retry of uncertain financial POST.

### CSH-FE-013 — Global Refresh does not refresh refund requests (P2 candidate)

**Source evidence:** CashierPanel mounts refund table with onRefresh={handleRefresh} ([CashierPanel.tsx:293-297](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/CashierPanel.tsx#L293-L297)); handleRefresh only calls triggerDataReload for regular cashier datasets ([useCashierActions.ts:314-317](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/useCashierActions.ts#L314-L317)); refund hook re-fetches on filter change/mount ([useRefundRequests.ts:29-65](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/cashier/useRefundRequests.ts#L29-L65)) and only calls parent refresh after a successful process ([useRefundRequests.ts:83-87](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/cashier/useRefundRequests.ts#L83-L87)).

**Impact and qualification:** Current refund requests can remain stale despite a manual global refresh.

**Fail-first / safe direction:** Write synthetic refresh click test with current filter and verify a new refund GET; prevent callbacks from recursively triggering each other.

### CSH-FE-014 — Only first 50 refund requests are reachable (P2 candidate)

**Source evidence:** Backend list takes limit=50 by default and offset (max limit 200) ([force_majeure.py:274-294](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/force_majeure.py#L274-L294)); hook submits only status_filter ([useRefundRequests.ts:30-51](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/cashier/useRefundRequests.ts#L30-L51)); table badge is requests.length and has no paging controls ([RefundRequestsTable.tsx:32-57](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/cashier/RefundRequestsTable.tsx#L32-L57), [RefundRequestsTable.tsx:100-116](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/cashier/RefundRequestsTable.tsx#L100-L116)).

**Impact and qualification:** Cashier may miss actionable requests beyond first page, and badge reports returned length, not total.

**Fail-first / safe direction:** Fail-first with 51+ synthetic rows and an actionable row on page 2; add paging/load-more or backend total contract behind gate.

### CSH-FE-015 — Concurrent refund list requests have no freshness guard (P2 candidate)

**Source evidence:** Refund hook loadRequests is keyed by filter, and setRequests/setLoading is unconditional after await ([useRefundRequests.ts:22-65](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/cashier/useRefundRequests.ts#L22-L65)). Existing tests cover basic happy/failure path but no A/B overlap ([useRefundRequests.test.ts:32-82](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/cashier/__tests__/useRefundRequests.test.ts#L32-L82)).

**Impact and qualification:** Displayed requests may not correspond to selected status filter. Backend validates status transitions under lock, so no wrong transfer has been shown.

**Fail-first / safe direction:** Fail-first A/B response-order tests, stale error/late loading and unmount; use request epoch/abort with latest-only state writes.

### CSH-FE-016 — Completed refund status does not prove actual payout (P2 candidate)

**Source evidence:** UI button labels complete as Выплатить ([refundRequestsColumns.tsx:121-131](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/cashier/refundRequestsColumns.tsx#L121-L131)) and completed as Возвращено ([refundRequestsColumns.tsx:25-35](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/cashier/refundRequestsColumns.tsx#L25-L35)); hook posts action=complete ([useRefundRequests.ts:111-115](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/cashier/useRefundRequests.ts#L111-L115)). Backend only changes approved->completed and commits processed_by/at ([force_majeure_api_service.py:389-462](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/services/force_majeure_api_service.py#L389-L462)), and API documents complete as money already returned ([force_majeure.py:315-330](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/force_majeure.py#L315-L330)).

**Impact and qualification:** Operator may mistake recording a completed manual payout for executing a bank transfer. No bank transfer is shown in the service code; the manual workflow may be intended.

**Fail-first / safe direction:** Synthetic test to distinguish actual bank transfer from manual attestation. Require clear confirmation/payout reference or verified backend provider contract after policy approval; no automatic financial change.

### CSH-FE-017 — Load failure is simultaneously reported as an empty refund queue (P3 candidate)

**Source evidence:** Hook sets error but leaves requests=[] on failure ([useRefundRequests.ts:22-59](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/cashier/useRefundRequests.ts#L22-L59)). Table independently renders AppError when error and AppEmpty when !loading && requests.length===0 ([RefundRequestsTable.tsx:79-110](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/cashier/RefundRequestsTable.tsx#L79-L110)).

**Impact and qualification:** Conflicting messages reduce confidence in financial counts.

**Fail-first / safe direction:** Test initial rejection and valid empty success; ensure error and true empty are mutually exclusive and retry stays available.

### CSH-FE-018 — Refund processing lacks a synchronous single-flight guard (P3 candidate)

**Source evidence:** Hook sets processingId then starts POST with no ref guard ([useRefundRequests.ts:66-97](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/cashier/useRefundRequests.ts#L66-L97)); buttons are hidden only after render observes processingId ([refundRequestsColumns.tsx:81-133](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/cashier/refundRequestsColumns.tsx#L81-L133)). Backend process locks row then validates status ([force_majeure_api_service.py:389-449](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/services/force_majeure_api_service.py#L389-L449)), so a second identical transition should be rejected.

**Impact and qualification:** Duplicate command attempts/errors are possible; this does not prove duplicate bank payouts.

**Fail-first / safe direction:** Use deferred promise and two synchronous submissions, assert single POST with clear failure recovery; preserve backend locking.

### Group 3 bounded source checkpoint (2026-11-01)

Reviewed RefundRequestsTable.tsx, useRefundRequests.ts, refundRequestsContracts.ts, refundRequestsColumns.tsx, their unit/source contract tests and related CSS; the force_majeure.py GET/POST refund and deposit endpoints; ForceMajeureApiService, row-locking repository, refund/deposit models; backend CSRF, Vite proxy, frontend API client/runtime and cashier tab wiring. **No tests run**; findings remain SOURCE-OBSERVED / REPRO-PENDING.

**Confirmed design protections:** refund endpoints use Admin/Cashier RBAC ([force_majeure.py:274-340](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/force_majeure.py#L274-L340)); backend determines available_actions from canonical status ([force_majeure_api_service.py:465-471](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/services/force_majeure_api_service.py#L465-L471)); refund process reads an exclusive locked row, validates status, and releases claims only for rejected requests ([force_majeure_api_service.py:389-449](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/services/force_majeure_api_service.py#L389-L449)); deposit credit/use takes a locked patient balance and appends transactions ([force_majeure_api_service.py:520-601](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/services/force_majeure_api_service.py#L520-L601)). No unsupported claim of current double refund or broken deposit concurrency.

**Distinct money channels:** bank-transfer RefundRequest, manual completion, and PatientDeposit credit/transaction are not interchangeable. A deposit credit is not necessarily a row in RefundRequestsTable. The reviewed CashierPanel mounts the refund-request table but no dedicated deposit ledger view; whether a unified reconciliation interface is required is a product decision, not an established defect. Do not infer an actual bank transfer from the completed status alone.

**Priority for reproduction:** CSH-FE-011/012 (routing/CSRF), CSH-FE-014 (incomplete action list), CSH-FE-016 (manual completion truthfulness). CSH-FE-013/015/017/018 are UI refresh/freshness/action-guard tests. All remain provisional, no P0/P1 demonstrated, no application edits or gate executed.

### CSH-FE-019 — A printable receipt can be generated from unverified client list data (P2 candidate)

**Evidence:** [useCashierActions.ts L350–387](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/useCashierActions.ts#L350-L387) prints `buildReceiptPrintPayload(paymentRow)` in browser before querying any backend receipt; the server PDF is only a fallback when browser print window fails. [cashierPaymentContracts.ts L212–248](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/cashierPaymentContracts.ts#L212-L248) derives date/number/status/amount/services from row fields and even synthesizes a `PAY-<id>` number. Backend [_helpers.py L77–98](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_helpers.py#L77-L98) exposes `can_print_receipt=true` on all payment states, not solely settled payments; browser template [panelPrint.ts L1113–1144](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/services/panelPrint.ts#L1113-L1144) is prominently headed `ЧЕК ОБ ОПЛАТЕ`. The authoritative PDF endpoint exists at [_visits.py L125–141](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_visits.py#L125-L141). Source test [useCashierActions.test.ts L240–247](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/__tests__/useCashierActions.test.ts#L240-L247) explicitly expects no server call on successful popup.

**Potential impact and uncertainty:** A stale or grouped list row, or a pending/cancelled/refunded status, can be printed as a payment receipt using client-derived fields, possibly not matching the canonical payment. No falsified real receipt is demonstrated.

**Fail-first test and safe fix boundary:** Synthetic paid->refunded status drift, grouped row, and pending payment; verify print obtains server-supported receipt for exact ID or clearly marks client view as unofficial. Maintain existing backend receipt contract; payment/receipt changes require gate.

### CSH-FE-020 — Multi-service printable receipt item totals can exceed the charged total (P2 candidate)

**Evidence:** [cashierPaymentContracts.ts L157–175](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/cashierPaymentContracts.ts#L157-L175) maps each `services_names` entry to `price:totalAmount` and `total:totalAmount` regardless of service count. [panelPrint.ts L1009–1025](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/services/panelPrint.ts#L1009-L1025) prints those totals per service and [panelPrint.ts L1157–1169](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/services/panelPrint.ts#L1157-L1169) prints only one overall amount. Existing [cashierPaymentContracts.test.ts L126–132](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/__tests__/cashierPaymentContracts.test.ts#L126-L132) explicitly *pins* two service items priced 100 each when payment total is 100.

**Potential impact and uncertainty:** With two service names and 100 UZS payment, printed service rows sum to 200 UZS while printed total is 100 UZS. The backend history DTO may omit service breakdown: this is conditional on a row carrying multiple service names, not proof that every live cashier receipt is affected.

**Fail-first test and safe fix boundary:** Fail-first names-only two-service row; assert sum(line totals)=100 or display no invented per-service prices. Prefer server-provided allocation/receipt for real amounts, and do not split 100 heuristically.

### CSH-FE-021 — Successful server PDF fallback is reported as a printing failure (P3 candidate)

**Evidence:** [useCashierActions.ts L370–385](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/useCashierActions.ts#L370-L385) calls `getReceipt` when popup is blocked; on `success:true` it runs `notify.warning(print_dialog_failed)` without a successful fallback message. [usePayments.ts L395–415](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/hooks/usePayments.ts#L395-L415) downloads an actual `receipt_<paymentId>.pdf` and returns success. Backend [_visits.py L125–141](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_visits.py#L125-L141) generates the PDF.

**Potential impact and uncertainty:** The cashier receives a failure warning despite receiving the downloaded PDF; misleading but not evidence of a missing receipt or payment mutation.

**Fail-first test and safe fix boundary:** Synthetic window.open=null and mocked PDF success/error; success must report download rather than print dialog, and failure must be distinct.

### CSH-FE-022 — Session warning 'Extend' control does not extend the session (P2 candidate)

**Evidence:** [CashierDialogsLayer.tsx L398–426](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/views/CashierDialogsLayer.tsx#L398-L426) implements Extend as `dismissSessionWarning(); notify.info(session_extending)`. [useCashierSessionWarning.ts L34–65](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/useCashierSessionWarning.ts#L34-L65) exposes only onWarning/onExpired and dismiss state, no refresh action. Shared API client supports token refresh separately ([client.ts L207–254](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/api/client.ts#L207-L254)), but this button does not call it.

**Potential impact and uncertainty:** A cashier can believe they extended a session, although the existing JWT may expire during the next financial operation. A later automatic API refresh might occur independently; it does not make the button truthful.

**Fail-first test and safe fix boundary:** Synthetic near-expired token and button click; assert a real refresh/recovery is invoked and user sees its real outcome, or relabel button as dismiss. Avoid promising successful refresh before verification.

### CSH-FE-023 — Session expiration can hard-navigate over an in-flight financial command (P2 candidate)

**Evidence:** [useCashierSessionWarning.ts L34–49](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/useCashierSessionWarning.ts#L34-L49) immediately assigns `window.location.href='/login'` on expiry and does not check pending cashier operations. Meanwhile [useCashierActions.ts L178–216](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/useCashierActions.ts#L178-L216) and [useCashierActions.ts L323–347](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/useCashierActions.ts#L323-L347) await money commands. A pre-existing [usePendingAwareSessionExpiry.ts L1–37](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/hooks/usePendingAwareSessionExpiry.ts#L1-L37) explicitly documents and addresses the class of unconfirmed commit + hard navigation in another module, but the cashier still uses the basic warning hook.

**Potential impact and uncertainty:** If server commits while browser navigates away, cashier may lose the response and repeat payment/refund without reconciliation. This is an uncertainty window; actual duplicated charges are not proven.

**Fail-first test and safe fix boundary:** Synthetic pending payment and refund promises, fire expired event, assert no immediate hard navigation before command outcome is safely reconciled. Integrate with authoritative pending signal, never block logout indefinitely; mandatory security/payment gate.

### CSH-FE-024 — Refund form allows invalid amounts to reach the server instead of rejecting locally (P3 candidate)

**Evidence:** [CashierDialogsLayer.tsx L299–343](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/views/CashierDialogsLayer.tsx#L299-L343) uses type=number min=1/max=`refundPaymentAmount`, but submit is a separate onClick button, not a form validity check. [useCashierActions.ts L323–345](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/useCashierActions.ts#L323-L345) validates only non-empty amount and reason length, uses parseFloat on the input and sends it; [useCashierDialogs.ts L125–138](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/useCashierDialogs.ts#L125-L138) stores original payment amount and prefilled outstanding amount separately. Backend [_helpers.py L220–224](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_helpers.py#L220-L224) enforces refund amount >0 and [_payments.py L1147–1189](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L1147-L1189) atomically rejects refunds exceeding remaining amount.

**Potential impact and uncertainty:** Bad or excessive amounts reach the API and cause preventable validation/errors, not successful negative/over-limit refunds based on inspected guards. Rendered max may exceed refundable remainder.

**Fail-first test and safe fix boundary:** Test negative/zero/NaN/exponent/beyond available remainder and valid partial amounts; fail closed in UI with exact backend remaining amount. Keep backend invariant authoritative.

### CSH-FE-025 — History sort controls are mouse-only table header elements (P3 candidate)

**Evidence:** [CashierHistoryTable.tsx L98–114](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/views/CashierHistoryTable.tsx#L98-L114) wires onClick to bare `<th>` for date/patient/amount; no `<button>`, tabIndex, keyboard callback or `aria-sort`. The current sort hook [useCashierSort.ts L14–32](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/useCashierSort.ts#L14-L32) supports toggling but not accessible semantics.

**Potential impact and uncertainty:** Keyboard-only users cannot reliably change sort and screen readers cannot determine the active sort direction.

**Fail-first test and safe fix boundary:** React Testing Library keyboard tab and Enter/Space plus axe header test; wrap title in real button, and add aria-sort to current column's th.

### CSH-FE-026 — Cashier hotkeys override native shortcuts while editing payment forms (P3 candidate)

**Evidence:** [useCashierActions.ts L116–139](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/useCashierActions.ts#L116-L139) registers Ctrl+F, F5, Ctrl+R, Ctrl+E and claims only to handle non-input focus, but provides no element guard. Shared [useHotkeys.ts L34–67](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/hooks/useHotkeys.ts#L34-L67) globally catches keyboard events on document and immediately `preventDefault`/invoke action, without an input/dialog exclusion.

**Potential impact and uncertainty:** While typing a refund reason or editing a payment amount, Ctrl+E can initiate export and Ctrl+F takes focus from the form; F5/Ctrl+R replace browser actions. Not a payment write by itself.

**Fail-first test and safe fix boundary:** Focus textarea/input inside an active dialog, dispatch shortcuts and assert browser editing shortcuts are untouched or explicitly scoped; preserve intentional navigation when form is not active.

### CSH-FE-027 — Hourly stats action ignores the selected range-mode filter (P3 candidate)

**Evidence:** [CashierPanel.tsx L180–207](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/CashierPanel.tsx#L180-L207) makes dateMode/dateFrom/dateTo visible in filters while always showing hourly stats button. Yet [useCashierActions.ts L390–398](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/useCashierActions.ts#L390-L398) loads stats by `target_date:selectedDate` alone, and [CashierDialogsLayer.tsx L348–355](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/views/CashierDialogsLayer.tsx#L348-L355) labels the modal using the same selectedDate. [useCashierWorklistData.ts L94–107](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/useCashierWorklistData.ts#L94-L107) uses dateFrom/dateTo for the other datasets when dateMode=range.

**Potential impact and uncertainty:** The hourly chart can silently show the old single-day selection while all other cashiers' metrics show the chosen multi-day period. Backend hourly endpoint accepts target_date, so interpreting a range requires explicit UI policy.

**Fail-first test and safe fix boundary:** Switch to range, click hourly analytics; show an explicit single-day selector/mode or valid range aggregation contract, not silently stale selectedDate.

### Group 4 bounded source checkpoint (2026-11-01)

Reviewed all 435 lines of `CashierDialogsLayer.tsx`; reducer/hook `useCashierDialogs.ts`; `useCashierSessionWarning.ts` and shared `useSessionTimeoutWarning.ts` plus pending-aware alternative; `useCashierActions.ts` print, refund, cancel, hotkeys and hourly stats; receipt payload builder `cashierPaymentContracts.ts`, `panelPrint.ts`, `printWindow.ts`; `CashierHistoryTable.tsx` actions and sortable headers; `CashierPanel.tsx` filters/toolbar; backend receipt endpoint, refund schema/invariant and payment available-action contract. Examined source unit tests for action/reducer/receipt/i18n; none executed.

**Positive source evidence:** backend cashier GET receipt produces authoritative PDF behind Admin/Cashier RBAC ([_visits.py L125–141](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_visits.py#L125-L141)); refund backend validates positive amount and atomic remaining debt ([_helpers.py L220–224](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_helpers.py#L220-L224), [_payments.py L1147–1189](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L1147-L1189)), so CSH-FE-024 is not a server money-integrity bypass. Browser-print utility sanitizes HTML before document.write ([printWindow.ts L1–16](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/utils/printWindow.ts#L1-L16)). History actions are still gated by backend-provided available_actions ([CashierHistoryTable.tsx L159–200](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/views/CashierHistoryTable.tsx#L159-L200)), and generic Dialog components may already handle focus-trapping; this audit does NOT assert a focus-trap defect without browser verification.

**Top priorities for synthetic reproduction:** CSH-FE-019/020 (receipt truth and arithmetic), CSH-FE-022/023 (session truth and pending mutation), then smaller UX CSH-FE-021/024–027. CSH-FE-004 remains a separate history grouping/action defect; do not duplicate it as a new receipt-specific root cause. No evidence of actual duplicate payment, provider settlement failure, or incorrectly paid real patient; all new findings `SOURCE-OBSERVED / REPRO-PENDING`.

**Still open:** Group 5 end-to-end API/backend/provider contract and regression coverage. Passing tests, live browser, real auth, CI status, financial-policy decisions and gate for implementation are not established in this docs-only audit.

### CSH-FE-028 — Cashier pending debt and grouped allocation disagree with canonical unrefunded balances (P2 candidate)

**Evidence:** [_payments.py L106–115](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L106-L115) selects paid/completed payments, then [_payments.py L178–206](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L178-L206) adds payment.amount without subtracting refunded_amount, filtering rows by this understated remaining debt. [_stats.py L90–116](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_stats.py#L90-L116) repeats gross aggregation for pending_count/pending_amount, and [_helpers.py L294–305](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_helpers.py#L294-L305) feeds gross values to grouped allocation [_payments.py L431–463](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L431-L463). In contrast canonical [payment_invariant_service.py L233–259](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/services/payment_invariant_service.py#L233-L259) explicitly sums `max(amount-refunded_amount,0)` and [_payments.py L1116–1173](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L1116-L1173) supports partial refunds without changing status from paid. Source integration coverage for net billing exists at [test_registrar_partial_payments.py L107–168](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/tests/integration/test_registrar_partial_payments.py#L107-L168), but does not prove these cashier view/grouped paths.

**Potential impact and uncertainty:** After a partial 70-of-100 refund from a paid 100 visit, canonical settled amount is 30 and debt 70, whereas cashier group readers can still see 100 paid/0 outstanding. If combined with an unpaid second visit, grouped allocation may reject or misallocate a legitimate amount. This is a code-path inconsistency; no real lost payment established.

**Fail-first / safe direction:** Fail-first synthetic visit services total 100, paid payment amount 100 refunded_amount 70, still status paid; assert pending list, stats, grouped candidate/allocation and canonical compute_paid_amount all agree on due 70. Cover mixed visits, fully refunded and overpayment policy; use backend SSOT and mandatory financial gate.

### CSH-FE-029 — Online status polling captures a stale null payment identifier (P2 candidate)

**Evidence:** [PaymentWidget.tsx L94–111](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/payment/PaymentWidget.tsx#L94-L111) initializes paymentData=null; [PaymentWidget.tsx L193–213](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/payment/PaymentWidget.tsx#L193-L213) memoizes startPolling with dependencies [clearPolling,t], but the interval calls `checkPaymentStatus` defined later. That handler [PaymentWidget.tsx L337–360](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/payment/PaymentWidget.tsx#L337-L360) exits if !paymentData?.payment_id. The provider-init path [PaymentWidget.tsx L264–313](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/payment/PaymentWidget.tsx#L264-L313) sets paymentData and schedules a timeout that invokes `startPolling` from the **pre-response render**, with no current-payment ref passed into the timer. Existing [PaymentWidget.contract.test.tsx L10–16](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/payment/__tests__/PaymentWidget.contract.test.tsx#L10-L16) merely asserts the status URL string, not interval behavior.

**Potential impact and uncertainty:** Auto-check may increment to the attempt cap without sending even one status GET; staff sees no confirmed success until a manual check. Exact React scheduling has not been exercised in browser.

**Fail-first / safe direction:** Fake-timer RTL test for successful initialization, provider URL and 5s interval, assert canonical GET uses current payment ID and one onSuccess; test unmount/timer cleanup. Use parameterized payment ID or latest ref and avoid stale closure.

### CSH-FE-030 — Payment provider list can refetch indefinitely on renders (P2 candidate)

**Evidence:** [useTranslation.ts L60–85](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/i18n/useTranslation.ts#L60-L85) allocates a fresh function `t` on every hook render. [PaymentWidget.tsx L127–156](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/payment/PaymentWidget.tsx#L127-L156) uses `useCallback(loadProviders,[currency,t])` and `useEffect(...,[loadProviders])`; each successful load invokes setProviders(newArray), setSelectedProvider, setProvidersLoading(false), triggering another render and another new t function. Provider selector can also reset to the first choice on every cycle.

**Potential impact and uncertainty:** Repeated GET /payments/providers, flickering loading state and selected-provider resets could block initiation or burden the API. Runtime fetch-loop count not yet measured.

**Fail-first / safe direction:** Fake stable provider response, RTL render/rerender with controlled translation; assert one initial GET per currency change, no perpetual fetch, preserve manual provider selection. Fix dependency identity or use a stable callback/ref without disabling correctness lint.

### CSH-FE-031 — Status monitoring timeout is misrepresented as failed payment (P2 candidate)

**Evidence:** [PaymentWidget.tsx L193–213](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/payment/PaymentWidget.tsx#L193-L213) marks `setPaymentStatus('failed')` on reaching MAX_POLLING_ATTEMPTS; [PaymentWidget.tsx L437–449](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/payment/PaymentWidget.tsx#L437-L449) presents failed/error alert for that state. Neither the interval expiration nor failed status is a canonical backend status; it can be a transport/monitoring timeout while the payment remains pending. The canonical GET [PaymentWidget.tsx L337–355](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/components/payment/PaymentWidget.tsx#L337-L355) only applies true backend status if a response arrives.

**Potential impact and uncertainty:** Staff may retry a charge while the provider transaction remains in progress; a later provider success can contradict a locally asserted failure. No real double charge reproduced.

**Fail-first / safe direction:** Use an explicit unknown/monitoring-timeout state and a query/reconciliation action; fake timers + pending provider responses + later paid status, assert no invented failed settlement.

### CSH-FE-032 — Cashier financial export silently drops records beyond 10,000 (P2 candidate)

**Evidence:** [_payments.py L825–853](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L825-L853) advertises `Экспорт всех платежей за период`, yet applies `.limit(10000)` to its descending query. Returned streaming CSV [_payments.py L898–911](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L898-L911) does not identify truncation or supply a continuation cursor. [usePayments.ts L331–354](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/hooks/usePayments.ts#L331-L354) downloads the file and reports success without verifying total row count.

**Potential impact and uncertainty:** Larger financial periods can produce incomplete reconciliation exports while appearing complete, especially relevant for historical clinic reports. Does not prove a specific dataset exceeds 10k.

**Fail-first / safe direction:** Back-end synthetic 10001 payment export, assert all records included via pagination/streaming or explicit partial-export marker and multi-file navigation; do not suggest unbounded memory query. Add scope/size warning visible to cashier.

### CSH-FE-033 — CSV export incorrectly labels refunded payments as pending (P3 candidate)

**Evidence:** [_payments.py L875–895](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L875-L895) maps paid/completed=>Оплачено; cancelled=>Отменён; all remaining values=>Ожидает. `refunded` is a canonical status explicitly produced when a full refund succeeds ([_payments.py L1239–1255](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L1239-L1255)) and visible in the cashier status mapping [cashierPaymentContracts.ts L250–275](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/cashierPaymentContracts.ts#L250-L275).

**Potential impact and uncertainty:** Downloaded refund reconciliation mislabels a returned transaction as awaiting payment; it does not change database status.

**Fail-first / safe direction:** Synthetic CSV statuses including refunded, pending, processing, failed, void and paid; preserve explicit status vocabulary or correctly map all canonical values. Tie regression to backend status enumeration.

### CSH-FE-034 — Financial CSV contains untrusted cells without formula-injection protection (P2 candidate)

**Evidence:** [_payments.py L869–896](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L869-L896) uses csv.writer directly with patient.short_name() and payment.note. CSV quoting prevents delimiter breakage, **not** spreadsheet formula interpretation when opened in Excel/other spreadsheet software. The registrar export has a separate explicit formula-neutralization rule [registrarCsv.ts L82–94](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/registrar/registrarCsv.ts#L82-L94), showing an existing project precedent.

**Potential impact and uncertainty:** A malicious or malformed patient name/payment note could be interpreted as a spreadsheet formula by a cashier opening the export. This is a potential spreadsheet injection risk, not evidence of exploitation or code execution.

**Fail-first / safe direction:** Synthetic formula-like and ordinary patient/notes cells; assert spreadsheet-safe escaping while preserving intended data and UTF-8, not blanket stripping; verify Excel/LibreOffice behavior only in isolated tests. Security gate for implementation.

### CSH-FE-035 — Invalid 200 cashier read model is silently accepted as zero records (P2 candidate)

**Evidence:** [usePayments.ts L102–115](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/hooks/usePayments.ts#L102-L115) casts response.data to Record and uses `data.items || []`; [usePayments.ts L157–170](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/hooks/usePayments.ts#L157-L170) repeats it for history and always returns success:true with pagination fields cast as numbers. The worklist hook [useCashierWorklistData.ts L150–161](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/frontend/src/pages/cashier/useCashierWorklistData.ts#L150-L161) treats success:true as confirmed list state. The backend explicitly publishes `items,total,page,size,pages` for pending [_payments.py L254–260](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_payments.py#L254-L260) and history via PaginatedResponse [_helpers.py L151–159](https://github.com/drsapaev/final/blob/a770ce3373b6e4b69f54b51723e1f2775dac4088/backend/app/api/v1/endpoints/cashier/_helpers.py#L151-L159).

**Potential impact and uncertainty:** A transient proxy/error JSON that returns HTTP 200 but violates the API contract can clear or mispage the cashier view with no schema error. Distinct from CSH-FE-001, which covers HTTP/request failures.

**Fail-first / safe direction:** Synthetic malformed 200 response, partial shape and valid empty envelope. Validate response at the API boundary and surface 'invalid read model' without inventing financial zero; no broad alias fallback.

### Group 5 cross-layer and CI checkpoint (2026-11-01)

**Source checks performed:** Reviewed the complete active `usePayments.ts` hook GET/POST/CSV/receipt methods, shared API client auth/CSRF/response handling, `PaymentWidget.tsx` provider loading/init/auto-poll and its source-only contract test, `CashierPanel` wiring, three cashier backend endpoint modules and `_helpers.py`, PaymentInvariantService, PaymentReadService, PaymentInitService, `/payments/init` request/response contracts, refunds and deposits from Group 3, and relevant source tests under `frontend/src/pages/cashier/__tests__`, `frontend/src/components/cashier/__tests__`, `frontend/src/components/payment/__tests__`, `backend/tests/unit`, `backend/tests/integration`. Tests found (but **not executed**) include registrar partial payment/refund regression and PostgreSQL force-majeure refund/deposit concurrency. A 18-line PaymentWidget contract test checks static route text, not polling behavior.

**Sources of truth confirmed:** Main cashier API `/api/v1/cashier` uses Admin/Cashier guards; `/api/v1/payments/init` permits Admin/Registrar/Cashier. Grouped payment endpoint enforces one patient, server-side allocation and a single transaction. PaymentInvariantService accounts for partial refunds. Cashier historical payment actions depend on `available_actions`; CSV and PDF responses are documented as streaming bytes. Online settlement is provisioned via pending provider payment and status/webhook path; do not treat merely initialized as paid. No actual provider live credentials, real charge or refund executed.

**CI observation on Draft PR #3813 HEAD `884f8740ffc6d64e90f6d55e9972b04f6678a346`:** GitHub Actions runs showed Unified CI **success**, Gitleaks **success**, Security **success**, Agent Workflow Guards **success**, but PR Review Quality Gate **failure** (run `41244794584`, job `124665868237`). Log explicitly says the PR body lacked mandatory `## Summary`, `## Cyclic Execution Evidence`, `## Contract Impact`, `## RBAC / Permissions`, `## Notification / Realtime`, `## Frontend Resilience`, `## Scope Gate`, `## Validation`. Gate's own 19 unit tests passed. This is a **PR description completeness failure**, **not** failing cashier functionality tests. PR body should be updated using docs-only sample without fabricated local test evidence; later run status must be checked separately. A combined commit status only showed Vercel success for main `a770ce3373b6e4b69f54b51723e1f2775dac4088`; neither status claim certifies live payments.

**Coverage gap:** Source-only contract tests and available backend tests do not prove end-to-end cashier cash split, refund balance readback, grouped allocation on refunded receipts, auto-poll callbacks, provider-list stable GET count, timeout vs failed semantics, Excel-safe/export-complete CSV, invalid successful HTTP response handling, browser PDF truthfulness or authenticated 403/CSRF recovery. Prioritize deterministic synthetic fail-first tests over snapshot/source-substring assertions. No local Vitest, pytest, Playwright, browser or mandatory `run_agent_gate.ps1` executed in this audit; no API writes and no production access.

**Suggested one-PR-at-a-time remediation order (not executed):** (a) CSH-FE-028 net refund debt/allocation server SSOT + 007 partial default; (b) CSH-FE-011/012 canonical refunds API and auth/CSRF; (c) CSH-FE-029/030/031 online polling/provider load/timeout (review CSH-FE-010 local smoke in same domain but separate root cause); (d) CSH-FE-004/019/020 receipt identity and item totals; (e) CSH-FE-008/023 command uncertainty and session logout; (f) CSH-FE-014/032/033/034 complete safe exports and refund lists; (g) remaining filter, resilience, accessibility and reporting items. Every change involving finance, security, API commands/contracts and patient data requires the repository's mandatory agent gate plus independent regression proof. Do not merge/deploy the documentation PR as a fix for any runtime issue.

**Review conclusion:** All **five named source-review groups** now have bounded source coverage. This is **SOURCE REVIEW COMPLETE (BOUNDED)**, not exhaustive line-by-line review of every indirect frontend dependency, not confirmation of browser/runtime behavior, and not verification that any source-observed finding has been reproduced or fixed. Every CSH-FE-001–035 remains provisional until test or browser evidence; conditional semantics (e.g. tender policy and manual payout attestation) require owner decisions.

### Post-merge follow-up review — 2026-11-02 (main `a50f7c40a043d1d749a164684e53d25cfe2ae094`)

Follow-up review of #3814 (`f82fb2ab`, the CSH-FE-028 net-of-refund debt fix), already merged into `main` (current HEAD `a50f7c40a043d1d749a164684e53d25cfe2ae094`, reconfirmed via `git ls-remote`). No new P0/P1 was found in the changed lines: pending-list/stats/grouped-allocation debt now correctly subtracts partial refunds via the canonical invariant. One divergence stays unclassified as an error and is recorded below as an open question so it is not lost. Because #3814 is already merged, any fix must be a NEW commit/PR, never an edit to the original PR branch.

### CSH-FE-036 — Payment stats totals: gross vs net-of-refunds semantics undecided (open question, not classified as a defect)

**Evidence:** After #3814, pending debt is refund-aware via the canonical invariant ([_stats.py L90–L94](https://github.com/drsapaev/final/blob/a50f7c40a043d1d749a164684e53d25cfe2ae094/backend/app/api/v1/endpoints/cashier/_stats.py#L90-L94), CSH-FE-028 marker). The same endpoint's receipt totals, however, still sum ORIGINAL amounts: [_stats.py L56–L71](https://github.com/drsapaev/final/blob/a50f7c40a043d1d749a164684e53d25cfe2ae094/backend/app/api/v1/endpoints/cashier/_stats.py#L56-L71) adds `p.amount` for status `paid`/`completed` into `total_amount`/`cash_amount`/`card_amount` with no refund subtraction; fully `refunded` payments only increment `cancelled_count` ([_stats.py L72–L73](https://github.com/drsapaev/final/blob/a50f7c40a043d1d749a164684e53d25cfe2ae094/backend/app/api/v1/endpoints/cashier/_stats.py#L72-L73)), and partial refunds on paid payments do not reduce these sums at all. `pending_amount` in the same response is net-aware, so the endpoint currently mixes two semantics in one payload.

**Open decision required (from the review):** must `total_amount`/`cash_amount`/`card_amount` mean gross receipts (current behavior) or receipts net of refunds? Until the owner decides, this divergence is NOT classified as an error. Whatever the answer: document it in the endpoint contract and pin it with a test — paid 100 + partial refund 30 must show 100 (gross) or 70 (net) consistently, and fully refunded payments must be included or excluded per the decision.

**Validation boundary:** source review only; no tests were executed for this entry.

## Initial source positives / boundaries

- The panel uses the canonical backend-provided `can_create_direct_payment` and `can_create_grouped_payment` in action availability ([CashierPendingTable.tsx L145–L169](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/frontend/src/pages/cashier/views/CashierPendingTable.tsx#L145-L169)), rather than guessing payment eligibility from display status.
- Cashier API `GET /pending-payments` is protected by Admin/Cashier role dependency ([backend/_payments.py L36–L45](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/backend/app/api/v1/endpoints/cashier/_payments.py#L36-L45)); pending rows are grouped and paginated on backend. These facts do not prove overall authorization of every mutation.
- Grouped payment allocation is backend-owned with one commit, direct payments have Visit locking. Full provider settlement, refunds, receipts and real-world financial idempotency are not verified; Groups 3–5 remain open.

## Change log

| Day | Scope | Result | Validation |
| --- | --- | --- | --- |
| 2026-11-01 | Cashier active-source inventory + partial Group 1 | Enumerated direct page and component files from GitHub; read cashier panel, read hooks, active tables, existing tests and pending endpoint. Registered three provisional issues CSH-FE-001–003 | Read-only GitHub source checks. No tests, build, lint, browser, gate or backend writes. |
| 2026-11-01 | Cashier Group 1 / Group 2 core | Added CSH-FE-004–010 (history grouping/action identity, locale sort, patient deep links, partially paid default, repeat submit, tender policy and local online smoke). Group 1 bounded source done; Group 2 core reviewed with provider contract deferred | GitHub code and existing test reads only; fresh-main compare 1 commit and no cashier React changes. No Vitest, pytest, browser, CI or gate. |
| 2026-11-01 | Cashier Group 3 refunds/deposits/RBAC | Added CSH-FE-011–018: wrong URL root, missing CSRF/refresh, global refresh gap, 50-item cap, filter response races, manual completion vs payout, error/empty UX, duplicate action. Backend role/locking and deposits verified at source level | GitHub read-only inspection. No automated tests, browser, payment mutation or gate. |
| 2026-11-01 | Cashier Group 4 dialog/receipt/session/keyboard source audit | Added CSH-FE-019–027: unverified client-side receipt, duplicated service totals, misleading PDF fallback toast, fake session extension, logout during pending money command, local refund validation, sortable header accessibility, hotkey focus hijack, hourly date scope | GitHub source and existing test reads only. No Vitest, Playwright, backend tests, gate, financial mutations or app changes. |
| 2026-11-01 | Cashier Group 5 source contracts/provider/CI audit | Added CSH-FE-028–035: net refund mismatch, stale online polling, provider effect refetch loop, wrong timeout status, truncated exports, refunded CSV mislabel, CSV formula injection, malformed 200 envelope. Reviewed relevant backend service, routes and existing tests. CI log explains PR template red gate | GitHub source and CI read-only checks; no runtime tests/browser or actual payment. All findings provisional. |

| 2026-11-02 | Post-merge follow-up review of #3814 (f82fb2ab) | Added CSH-FE-036 open question: `/cashier/stats` totals/cash/card remain gross sums of original payment amounts while pending debt is now net-of-refunds; owner decision required. No new P0/P1 in #3814's changed lines | Source review at main `a50f7c40a043d1d749a164684e53d25cfe2ae094`; no tests executed |

## Closure

Each of the original five groups must be marked done **only** after every named direct file has been reviewed, relevant source tests and backend contracts checked, and repeated findings deduplicated. Even then distinguish `SOURCE REVIEW COMPLETE` from `TEST-REPRODUCED / FIXED`; avoid the prior registrar ambiguity of claiming every frontend file was covered.

