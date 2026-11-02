# Registrar + cashier frontend: follow-up source review and coverage gaps (2026-11-02)

> Documentation-only Draft audit. Source-observed candidates; no executed reproduction, no claim of production impact. Do **not** merge as a code fix.

## Baseline and scope

- Repository: `drsapaev/final`; reviewed `main` at `ee7763e77e545db1479e257dbe4d3a388264cc03` (the commit matched `main` immediately before this audit branch).
- Prior audit indices are [registrar Draft PR #3803](https://github.com/drsapaev/final/pull/3803) (`docs/audits/2026-10-29-registrar-frontend-review-ledger.md`) and [cashier Draft PR #3813](https://github.com/drsapaev/final/pull/3813) (`docs/audits/2026-11-01-cashier-frontend-review-ledger.md`). **Those remain the original historical ledgers.**
- Mode: `direct_execute` for a **new, single Markdown source-review checkpoint only**. Allowed edit: `docs/audits/2026-11-02-registrar-cashier-followup-source-review.md`. Source/test/backend reads are reference-only. No gate executable was run because no queue/payment/security/clinical application contract or code was changed. All later executable repairs require the mandatory gate and execution prompt under `AGENTS.md`.
- Denied writes: `frontend/**`, `backend/**`, database/migrations, workflows, secrets, other branches/ledgers, live data, deployments. Stop condition: do not implement fixes or silently close prior findings inside this documentation PR.
- Method: GitHub pinned file reads and cross-checks against the actual producer/backend DTO, not a browser run. Severity labels are **provisional** until synthetic fail-first tests demonstrate behavior.

## Answer to 'what frontend files remain to review?'

The previous reviews **already inspected all five named registrar groups** and the cashier page-local nine files, six view files, and four refund-component files to a **bounded** source level. Thus it would be inaccurate to call these paths completely unreviewed. The remaining work is deeper branch/contract review and execution proofs, not another first-pass inventory of the same files.

| Area | Remaining incomplete depth or verification | Exact files / scope | Status after this pass |
| --- | --- | --- | --- |
| Registrar wizard | Full branch-by-branch review of registration/edit/multiservice execution, race/idempotency and date-dependent flow; original audit explicitly described a targeted scan of a 3331-line wizard and 2343-line utility | `frontend/src/components/wizard/AppointmentWizardV2.tsx`; `frontend/src/components/wizard/wizardUtils.ts`; remaining components/tests under `frontend/src/components/wizard/` | **Still incomplete**; not proven by running tests |
| Registrar preview/identity display | Route-reachable preview dialogue and its value formatter, including canonical ticket facts | `frontend/src/pages/registrar/views/RecordPreview.tsx`; `frontend/src/pages/registrar/registrarHelpers.ts`; `frontend/src/pages/registrar/views/RegistrarDialogsLayer.tsx`; `frontend/src/pages/registrar/registrarQueueAdapter.ts` | **Focused source check done now**; new REG-FE-067 |
| Registrar auxiliary selectors/price approvals | Establish actual mounted reachability before calling any behavior a registrar production defect | `frontend/src/components/registrar/IntegratedServiceSelector.tsx`, `IntegratedDoctorSelector.tsx`, `PriceOverrideApproval.tsx` | Previously scanned; **active consumer still unproven**; do not count dormant issues |
| Registrar visual/a11y | Browser evidence for CSS, keyboard/focus/scrolling, accessibility and historic/doctor/resource switching | Registrar CSS, shared `ModernDialog`, `DataTable`, `EnhancedAppointmentsTable` and related Playwright/axe scenarios | Source review exists; **runtime/visual review incomplete** |
| Cashier refund presentation | Complete backend DTO-to-table check, including returned sum and refund destination | `frontend/src/components/cashier/refundRequestsColumns.tsx`, `refundRequestsContracts.ts`, `useRefundRequests.ts`, `RefundRequestsTable.tsx` | **Focused contract check done now**; new CSH-FE-037/038 |
| Cashier other presentation | Detailed edge-case review and test execution for filters/service badges/stats; compare cash vs refund vs zero vs missing field | `frontend/src/pages/cashier/views/CashierServiceBadges.tsx`, `CashierFiltersCard.tsx`, `CashierStatsCard.tsx`, `CashierPendingTable.tsx` | Targeted re-read now; remaining cross-component tests |
| Cashier mutation, provider, session | Source read was bounded, but concurrent/uncertain-payment, delayed provider response, CSRF, RBAC, double submit and stale read A/B sequences were **not executed** | `frontend/src/components/payment/PaymentWidget.tsx`, `CashPaymentModal.tsx`, `frontend/src/hooks/usePayments.ts`, `frontend/src/api/client.ts`, `frontend/src/hooks/usePendingAwareSessionExpiry.ts` | Deep test/e2e coverage still required; see existing CSH-FE IDs before issuing new IDs |
| Cashier print/export/visual | Source reviewed for defects but no full receipt/PDF reconciliation, CSV injection or actual browser/layout validation | `frontend/src/services/panelPrint.ts`, `frontend/src/utils/printWindow.ts`, `frontend/src/pages/cashier.css`, `frontend/src/components/cashier/RefundRequestsTable.css` | **Still needs** synthetic end-to-end, visual and physical print checks |

**Distinction:** 'reviewed' means code was read; 'confirmed fixed' requires an executable regression and a merged fix PR. Old indices already include REG-FE-001–066 and CSH-FE-001–036 (including post-merge open questions); do not duplicate them in this new pass. Reconcile their statuses with current main separately.

## New indexed findings (not previously recorded under these IDs)

| ID | Priority candidate | Surface | Source observation | Verification |
| --- | --- | --- | --- | --- |
| **REG-FE-067** | P2 | Registrar record preview | 'Очередь' formats objects by queue name/tag but discards their `number` | SOURCE-OBSERVED / REPRO-PENDING |
| **CSH-FE-037** | **P1** | Cashier refund requests amount | Backend responds `refund_amount`; table column reads `amount`; no adapter maps between them | SOURCE-OBSERVED / REPRO-PENDING |
| **CSH-FE-038** | P2 | Cashier refund destination | UI maps every type except `deposit` to 'На карту', including the legitimate `cash` refund enum | SOURCE-OBSERVED / REPRO-PENDING |

### REG-FE-067 — Record preview shows queue label, not issued ticket (P2 candidate)

**Producer/consumer proof:** The live `RegistrarDialogsLayer` mounts `RecordPreview` ([L136](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/pages/registrar/views/RegistrarDialogsLayer.tsx#L136)). `RecordPreview.tsx` [L58](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/pages/registrar/views/RecordPreview.tsx#L58) renders the queue field as `formatPreviewList(row.queue_numbers)`. The formatter in `registrarHelpers.ts` [L322–327](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/pages/registrar/registrarHelpers.ts#L322-L327) selects `name`, `service_name`, `code`, `queue_name` or `queue_tag` and **never reads `number`**. Meanwhile `registrarQueueAdapter.ts` [L117–127](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/pages/registrar/registrarQueueAdapter.ts#L117-L127) produces `queue_numbers` records with `number`, `queue_tag` and `queue_name`.

**Repro (not run):** Provide a synthetic row with `{queue_number:17, queue_numbers:[{number:17,queue_tag:'cardiology',queue_name:'Cardiology'}]}` and open the record preview. The formatter returns `Cardiology`, not `№17`. Multi-queue rows likewise lose all their ticket numerals. This is a **display defect**, not evidence that the server issued a wrong ticket.

**Fail-first test / fix direction:** Mount `RecordPreview` with numbers 17 and 22 in distinct owner scopes; assert both issued numbers appear paired with the correct queue labels. A `null`/unallocated number should show a non-ticket placeholder and never invent a row ordinal. Prefer a dedicated ticket formatter reading the backend `queue_numbers` identity rather than changing generic `formatPreviewList` used for services. Keep server identity SSOT.

### CSH-FE-037 — Refund amount column uses nonexistent response field (P1 candidate)

**Server contract:** `RefundRequestResponse` in `backend/app/api/v1/endpoints/force_majeure.py` [L111–134](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/backend/app/api/v1/endpoints/force_majeure.py#L111-L134) declares `refund_amount: float` and does not declare `amount`. The domain serializer also explicitly returns `"refund_amount": float(req.refund_amount)` in `force_majeure_api_service.py` [L612](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/backend/app/services/force_majeure_api_service.py#L612).

**Frontend contract:** `refundRequestsContracts.ts` [L21](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/components/cashier/refundRequestsContracts.ts#L21) declares optional `amount`, not `refund_amount`; `useRefundRequests.ts` [L49–50](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/components/cashier/useRefundRequests.ts#L49-L50) assigns fetched objects without transforming the field; `refundRequestsColumns.tsx` [L156–158](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/components/cashier/refundRequestsColumns.tsx#L156-L158) uses column key `amount`, and its formatter [L66](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/components/cashier/refundRequestsColumns.tsx#L66) substitutes `—` for undefined.

**Impact hypothesis:** A legitimate 70,000 UZS refund request can show **no amount** next to approve/reject/complete actions. The backend may still validate commands; no incorrect payout is claimed. Severity P1 reflects financial-operator decision quality; validate with an executable test before treating this as confirmed.

**Fail-first test / fix direction:** Mock the **actual response DTO** containing `refund_amount:70000` and no `amount`, render `RefundRequestsTable` and assert `70 000` is visible in its amount cell. Include zero/invalid/missing cases, and ensure action states remain sourced from backend `available_actions`. Update the typed read model and column to `refund_amount`; do not synthesize totals client-side. Mandatory finance/API contract gate for the subsequent code PR.

### CSH-FE-038 — Cash refund is labeled 'to card' (P2 candidate)

**Backend:** `RefundType` enum in `backend/app/models/refund_deposit.py` [L46–50](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/backend/app/models/refund_deposit.py#L46-L50) has `bank_transfer`, `deposit`, and `cash`. **Frontend:** `getRefundTypeBadge` in `refundRequestsColumns.tsx` [L46–52](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/components/cashier/refundRequestsColumns.tsx#L46-L52) renders `На депозит` for `deposit` and the translation key for `На карту` for **every other value**. Thus `cash` is displayed as `На карту`; unknown future enum values would also be misleadingly labeled as card payouts.

**Fail-first test / fix direction:** Test all three known enum values and an unknown value. Deposit → deposit, cash → cash desk, bank transfer → bank/card wording that faithfully represents its actual destination, unknown → honest unknown. Derive the explicit vocabulary from the backend contract; use localization keys for RU/UZ/EN.

## De-duplication and source-positive checks

- CSH-FE-037 and -038 are **not** CSH-FE-011/012 (wrong refund API origin/CSRF), CSH-FE-014 (50-item pagination), CSH-FE-016 (whether completed means money transferred), nor CSH-FE-020 (receipt item totals). They concern the read-side refund list's displayed amount and type.
- REG-FE-067 is **not** REG-FE-022/056/062/063 (canonical ticket issuance/binding/aggregation); this is exclusively the preview's final formatter for an already provided number.
- Cashier `CashierServiceBadges.tsx`, `CashierFiltersCard.tsx`, `CashierStatsCard.tsx`, `refundRequestsColumns.tsx`, `refundRequestsContracts.ts`, `useRefundRequests.ts` and `RefundRequestsTable.tsx` were additionally read at current main. Lack of an executed test does not create additional findings by itself.
- This source pass verified `getRefundTypeBadge` is presentation-only and `hasBackendRefundAction()` stays fail-closed on action permission. No evidence of successful or failed real transfers was collected.

## Next bounded review cycles

1. **Cashier refund truth, first:** run a synthetic response DTO → `useRefundRequests` → `RefundRequestsTable` component test for CSH-FE-037/038; inspect user-readable refusal/error states. Create a separate gated implementation PR, not in this audit branch.
2. **Registrar preview, second:** verify current active preview trigger and component test, ensure multi-queue numbers carry owner identifiers, then repair display only under REG-FE-067 in a separate implementation PR.
3. **Registrar wizard deep pass:** trace the remaining wizard cart/price/doctor/time/confirm branches through `AppointmentWizardV2.tsx` and `wizardUtils.ts` in small slices; check against existing REG-FE issues before numbering anything new.
4. **Cashier payment provider/print:** run bounded source + synthetic defer/retry tests for `PaymentWidget`, `CashPaymentModal`, `usePayments`, `panelPrint`, `printWindow` and page-specific CSS in an actual browser. Existing CSH-FE-001–035 already cover many relevant hypotheses.
5. **Reachability boundary:** determine whether orphaned registrar selectors/price-approval components are actually mounted. Do not classify dormant code as a current registrar UX regression.


## Focused wizard review: AppointmentWizardV2.tsx + wizardUtils.ts (2026-11-02)

**Baseline:** `main ee7763e77e545db1479e257dbe4d3a388264cc03`. Read the two requested files (3331 and 2343 lines) with source-following into `CartStepV2.tsx`, `PatientStepV2.tsx`, `serviceCodeResolver.ts`, frontend focused tests, and `backend/app/services/registrar_edit_delta_service.py`. Read current `AGENTS.md` and repo SSOT skill. This is a **bounded deep source review**, not a line-by-line runtime proof or an executed test. Existing REG-FE-010–013, -016, -018, -037, -040/041, and other indexed findings retain their own IDs; these three root causes are distinct.

| ID | Provisional severity | Path | Symptom | Verification status |
| --- | --- | --- | --- | --- |
| **REG-FE-068** | **P1** | `wizardUtils.ts` + `AppointmentWizardV2.tsx` | Removing one of two services that share one queue entry is silently treated as no service delta, then reported as a successful edit | **SOURCE-OBSERVED / REPRO-PENDING** |
| **REG-FE-069** | **P1** | `wizardUtils.ts` | Queue-entry ID equality is type-sensitive; `42` and `"42"` name the same entry but a still-kept entry is sent for cancellation | **SOURCE-OBSERVED / REPRO-PENDING** |
| **REG-FE-070** | P2 | `AppointmentWizardV2.tsx` | Manual service-list refresh announces success even when the fetch failed | **SOURCE-OBSERVED / REPRO-PENDING** |

### REG-FE-068 — Removing a single service within a retained queue entry is not a persisted edit (P1 candidate)

**Active route:** `CartStepV2.tsx` [L657–679](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/components/wizard/CartStepV2.tsx#L657-L679) offers the decrement-to-zero and remove buttons, calling the wizard's `removeFromCart`. The wizard [L1461–1469](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/components/wizard/AppointmentWizardV2.tsx#L1461-L1469) removes the entire cart item. `normalizeServicesFromInitialData` [L370–384, L488–499](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/utils/serviceCodeResolver.ts#L370-L499) can carry the same `original_queue_id` on two distinct service items from one queue.

**Loss of intent:** `buildEditDeltaTargetItems` [L1930–1983](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/components/wizard/wizardUtils.ts#L1930-L1983) iterates **current items only**, sending new services or changed quantities. Removed service A is absent, and unchanged B yields an empty payload. `getRemovedQueueEntryIds` [L463–474](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/components/wizard/wizardUtils.ts#L463-L474) sees the queue-entry ID still present in B and does not cancel the entry. The wizard's no-delta branch [L2484–2487, L2621–2669](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2484-L2669) then performs a patient update and can show success. Backend `RegistrarEditDeltaService.apply()` [L68–126](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/backend/app/services/registrar_edit_delta_service.py#L68-L126) loops over supplied `services`; an omitted A is not a delete instruction. Sending quantity zero through that contract is not a safe shortcut: the backend coerces requested quantity to at least one.

**Synthetic fail-first (not run):** Starting queue entry 42 has service A=1 and B=1. Open wizard in edit mode, remove A, leave B unchanged, confirm. Assert that A is removed in canonical backend and any invoice/visit adjustment is coherent; **or** that an explicit unsupported-operation error prevents a misleading success. This test currently has no defined remove-service command. Also cover A/B in separate queue entries (whole-entry cancellation) so the fix does not change existing cancel semantics.

**Fix boundary:** Backend SSOT must define the per-service removal/refund/visit transaction separately from cancelling the whole queue entry. Do not implement a client-side zero quantity, blind cancel, or optimistic success. Run mandatory `gate_known_root_cause` with full queue/visit/payment scope before implementation.

### REG-FE-069 — Mixed `string | number` queue-entry IDs can cancel a retained record (P1 candidate)

**Proof in pure comparison:** The helper signature explicitly accepts `Array<string | number>` and cart items with `original_queue_id?: string | number` in [wizardUtils.ts L458–474](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/components/wizard/wizardUtils.ts#L458-L474). It inserts raw cart IDs into `Set<string | number>` and filters original IDs with `!currentQueueIds.has(id)`. Therefore `getRemovedQueueEntryIds([42], [{original_queue_id: "42"}])` returns `[42]` instead of `[]`. `cancelRemovedQueueEntries` [L490–522](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/components/wizard/wizardUtils.ts#L490-L522) then issues `POST /online-queue/entries/42/cancel` even though the entry remains in the cart. The wizard also repeats this raw-Set comparison inline in [L2544–2556, L2649–2655 and L2815–2829](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2544-L2829).

**Reachability caveat:** Support for both types is explicit, but this source-only pass has **not proved** a current backend payload actually mixes types between original identity and cart. Severity is provisional and requires an actual adapter→wizard fixture before calling it a production incident. Existing `wizardCancelRemovedEntries.test.ts` only uses homogeneous numeric IDs; no mixed representation case is covered.

**Fail-first:** Feed canonical entry identity 42 and retained item `original_queue_id:"42"`; assert **zero** cancel API calls. Also test distinct IDs, missing/invalid identity, and a combined two-entry same-patient edit. Normalize *queue-entry* identity once (not DailyQueue.id, visit id or appointment id) and avoid mutation when ownership is ambiguous.

### REG-FE-070 — Service refresh signals success on network failure (P2 candidate)

The `loadServices` helper [AppointmentWizardV2.tsx L922–948](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/components/wizard/AppointmentWizardV2.tsx#L922-L948) catches a failed `fetchRegistrarServices`, logs it and **resolves normally**. The actual Step 2 refresh button calls `handleReloadServices` [L2897–2907 and L3097–3099](https://github.com/drsapaev/final/blob/ee7763e77e545db1479e257dbe4d3a388264cc03/frontend/src/components/wizard/AppointmentWizardV2.tsx#L2897-L3099): after `await loadServices()`, it always displays `toast.success`. Its catch is unreachable for fetch failures swallowed by the helper. This is not REG-FE-008 (Welcome manual refresh, separate UI/call chain).

**Fail-first:** Make `fetchRegistrarServices` reject on user-initiated refresh. Assert error/retry feedback, **no success notification**, no fabricated empty catalog and no unverified repricing. Resolve a subsequent request and assert one success notification. Use an explicit load result or propagate error to the header while preserving suitable resilience for background fetch.

### Verified source-positive guards and review limits

- Observed existing synchronous submit lock + idempotency payload binding and uncertain-outcome handling in the cart create path; no claim they are absent.
- Quote effect uses request-epoch guard and server quote token on create/edit/full update; this does **not** establish an executed live financial or queue contract test.
- Existing backend edit-delta supports **quantity change** for a given service; it is not a general remove-one-service API.
- Review did **not** perform Vitest, pytest, Playwright, browser smoke, PowerShell execution gate, staging or production changes. Findings retain `REPRO-PENDING`.
- Reproduction and any code changes belong to independent, domain-gated implementation PRs, not this documentation Draft.

## Validation and rollback

- Checked: prior audit indices, current repository `AGENTS.md`, project SSOT skill, canonical producer/consumer source and recent main commit via connected GitHub. Cross-checked the exact `refund_amount` name in both Pydantic and serializer; checked the actual `RecordPreview` consumer and `RefundType` enum.
- NOT run: local worktree state/PowerShell gate; Vitest/pytest/Playwright/axe; `git diff --check`; production or staging; CI for this newly created PR. Source review is **not a runtime test**.
- Rollback: revert this single Markdown commit or close the audit Draft. No data or application behavior changed.
- Stop: do not mark findings resolved or deploy until synthetic failing tests, mandatory domain gate for source fixes, independent review and successful required CI.
