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

1. **Group 1 — composition, data reads, filters and tables: SOURCE REVIEW IN PROGRESS.** Read `CashierPanel.tsx`, `useCashierWorklistData.ts`, `usePayments.ts` list getters, `CashierPendingTable.tsx`, `CashierHistoryTable.tsx`, existing `useCashierWorklistData.test.ts`; identified CSH-FE-001–003. Still review sorting/grouping, search/filter/date and full UI edge cases before marking done.
2. **Group 2 — financial commands and payment lifecycle: PENDING.** `useCashierActions.ts`, `cashierPaymentContracts.ts`, `CashPaymentModal.tsx`, `PaymentWidget.tsx`, `usePayments.ts` write helpers. Focus on payment commit uncertainty, grouped allocations, duplicate submissions, honest success and server authorization.
3. **Group 3 — refund requests, deposits and permissions: PENDING.** `RefundRequestsTable.tsx`, `useRefundRequests.ts`, columns/contracts, `/force-majeure/refund-requests` and cashier refund backend. Distinguish a refund request from a completed actual refund.
4. **Group 4 — dialogs, printing, filtering and accessibility: PENDING.** `CashierDialogsLayer.tsx`, UI views, receipt print path and toolbar. Verify role/action gating, keyboard UX, dates and error presentation.
5. **Group 5 — API/backend contracts and regression coverage: PENDING.** `usePayments.ts`, `api/client.ts`, cashier endpoints/services, exact HTTP error shapes, CSV/receipt and status/refund contracts, test coverage, no false claims about CI.

## Findings index

| ID | Provisional priority | Scope | Source-derived observation | Evidence status | Planned test |
| --- | --- | --- | --- | --- | --- |
| CSH-FE-001 | P2 | Pending/history read errors | Failed list request clears rows, no distinct failure/stale state; UI shows operational empty state | SOURCE-OBSERVED / REPRO-PENDING | failed refresh vs real empty response |
| CSH-FE-002 | P2 | Async query identity | Overlapping date/search/page requests can overwrite newer result; shared pending/history loading can clear prematurely | SOURCE-OBSERVED / REPRO-PENDING | deferred A/B out-of-order |
| CSH-FE-003 | P3 | Pending badge count | Tab badge uses current-page `appointments.length` instead of server `pendingTotalItems` | SOURCE-OBSERVED / REPRO-PENDING | 21 rows / page-size 20 |

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

## Initial source positives / boundaries

- The panel uses the canonical backend-provided `can_create_direct_payment` and `can_create_grouped_payment` in action availability ([CashierPendingTable.tsx L145–L169](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/frontend/src/pages/cashier/views/CashierPendingTable.tsx#L145-L169)), rather than guessing payment eligibility from display status.
- Cashier API `GET /pending-payments` is protected by Admin/Cashier role dependency ([backend/_payments.py L36–L45](https://github.com/drsapaev/final/blob/f308ed97e7f640a33e2bb255e23aaa109e69110a/backend/app/api/v1/endpoints/cashier/_payments.py#L36-L45)); pending rows are grouped and paginated on backend. These facts do not prove overall authorization of every mutation.
- No conclusion is yet recorded for grouped payment creation, refund handling, confirmation success, receipts, backend idempotency or financial concurrency. Those require Groups 2–5.

## Change log

| Day | Scope | Result | Validation |
| --- | --- | --- | --- |
| 2026-11-01 | Cashier active-source inventory + partial Group 1 | Enumerated direct page and component files from GitHub; read cashier panel, read hooks, active tables, existing tests and pending endpoint. Registered three provisional issues CSH-FE-001–003 | Read-only GitHub source checks. No tests, build, lint, browser, gate or backend writes. |

## Closure

Each of the original five groups must be marked done **only** after every named direct file has been reviewed, relevant source tests and backend contracts checked, and repeated findings deduplicated. Even then distinguish `SOURCE REVIEW COMPLETE` from `TEST-REPRODUCED / FIXED`; avoid the prior registrar ambiguity of claiming every frontend file was covered.

