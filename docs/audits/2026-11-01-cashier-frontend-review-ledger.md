# Cashier frontend audit ledger — 2026-11-01

> **Status:** IN PROGRESS / read-only SOURCE REVIEW, not a production-readiness or financial-safety certification.
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
3. **Group 3 — refund requests, deposits and permissions: PENDING.** `RefundRequestsTable.tsx`, `useRefundRequests.ts`, columns/contracts, `/force-majeure/refund-requests` and cashier refund backend. Distinguish a refund request from a completed actual refund.
4. **Group 4 — dialogs, printing, filtering and accessibility: PENDING.** `CashierDialogsLayer.tsx`, UI views, receipt print path and toolbar. Verify role/action gating, keyboard UX, dates and error presentation.
5. **Group 5 — API/backend contracts and regression coverage: PENDING.** `usePayments.ts`, `api/client.ts`, cashier endpoints/services, exact HTTP error shapes, CSV/receipt and status/refund contracts, test coverage, no false claims about CI.

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

## Initial source positives / boundaries

- The panel uses the canonical backend-provided `can_create_direct_payment` and `can_create_grouped_payment` in action availability ([CashierPendingTable.tsx L145–L169](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/frontend/src/pages/cashier/views/CashierPendingTable.tsx#L145-L169)), rather than guessing payment eligibility from display status.
- Cashier API `GET /pending-payments` is protected by Admin/Cashier role dependency ([backend/_payments.py L36–L45](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/backend/app/api/v1/endpoints/cashier/_payments.py#L36-L45)); pending rows are grouped and paginated on backend. These facts do not prove overall authorization of every mutation.
- Grouped payment allocation is backend-owned with one commit, direct payments have Visit locking. Full provider settlement, refunds, receipts and real-world financial idempotency are not verified; Groups 3–5 remain open.

## Change log

| Day | Scope | Result | Validation |
| --- | --- | --- | --- |
| 2026-11-01 | Cashier active-source inventory + partial Group 1 | Enumerated direct page and component files from GitHub; read cashier panel, read hooks, active tables, existing tests and pending endpoint. Registered three provisional issues CSH-FE-001–003 | Read-only GitHub source checks. No tests, build, lint, browser, gate or backend writes. |
| 2026-11-01 | Cashier Group 1 / Group 2 core | Added CSH-FE-004–010 (history grouping/action identity, locale sort, patient deep links, partially paid default, repeat submit, tender policy and local online smoke). Group 1 bounded source done; Group 2 core reviewed with provider contract deferred | GitHub code and existing test reads only; fresh-main compare 1 commit and no cashier React changes. No Vitest, pytest, browser, CI or gate. |

## Closure

Each of the original five groups must be marked done **only** after every named direct file has been reviewed, relevant source tests and backend contracts checked, and repeated findings deduplicated. Even then distinguish `SOURCE REVIEW COMPLETE` from `TEST-REPRODUCED / FIXED`; avoid the prior registrar ambiguity of claiming every frontend file was covered.

