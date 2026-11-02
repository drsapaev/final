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


## Focused auxiliary registrar selector review (2026-11-02, main `1595ce3dc907c64da57fd221de330646e4a9ed90`)

**Requested paths (source read):** `frontend/src/components/registrar/IntegratedDoctorSelector.tsx` (276 LOC), `IntegratedServiceSelector.tsx` (441 LOC), and `PriceOverrideApproval.tsx` (408 LOC). Cross-read `frontend/src/api/registrar.ts`, `frontend/src/hooks/useRegistrarApi.ts`, `frontend/src/App.tsx`, `frontend/src/pages/RegistrarPanel.tsx`, `backend/app/api/v1/endpoints/registrar_integration/_services_doctors.py`, `_queue_ops.py`, `backend/app/api/v1/endpoints/registrar_wizard/_cart.py`, `backend/app/models/visit.py`, and the existing `PriceOverrideApproval.contract.test.tsx`. Read installed React review skill and project SSOT repair skill. Note `main` has advanced since the audit branch was created at `ee7763e7`; the changes seen on current main include the merged Sentry fix #3804 and do not establish any of these components have a new runtime consumer.

### Critical reachability boundary (NO active registrar route proved)

Exact-identifier code search on current `main` returned each component's **own declaration**, API-wrapper comments, ADR mention, UI-baseline configuration, and a source-only PriceOverrideApproval contract test, but **no JSX import, route lazy import, barrel export used by a live consumer, or render call** for any of the three. `App.tsx` lazily mounts `RegistrarPanel`, which has no import of the three. This is **evidence of likely dormant UI**, not a proof that dynamic/plugin-loading is impossible. Neither `PriceOverrideApproval` nor the two selectors may be counted as a demonstrated **production registrar UI** problem without an actual mounted route or import trace.

**Prior finding, DO NOT duplicate:** `IntegratedServiceSelector` [L45–85, L126–183](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/registrar/IntegratedServiceSelector.tsx#L45-L183) contains hardcoded `DEMO_SERVICES` IDs/prices, sets them as selectable data before API resolution, and retains them on HTTP 401/403, other failures, or legitimate empty catalog responses. The default demo option IDs may collide with actual unrelated service records and the local sum is not a server quote. **Already explicitly unnumbered** in [registrar ledger PR #3803](https://github.com/drsapaev/final/pull/3803), at old ledger lines 536 and 795. It **must not** get a fresh REG-FE ID in this pass. Until these dormant components are removed or safely reactivated, never wire the demo selector to real booking actions.

### Newly distinct findings

| ID | Priority candidate | Evidence | Reachability/reproduction |
| --- | --- | --- | --- |
| **REG-FE-071** | P2 conditional | Doctor selector accepts `specialty` prop but does not filter fetched/rendered doctors by it | **DORMANT / SOURCE-OBSERVED / REPRO-PENDING** |
| **REG-FE-072** | P2 conditional | Doctor selector presents per-specialty static limits as actual doctor's queue number range | **DORMANT / SOURCE-OBSERVED / REPRO-PENDING** |
| **REG-FE-073** | P2 conditional | Price override list has no request-epoch guard for concurrent filter changes | **DORMANT / SOURCE-OBSERVED / REPRO-PENDING** |
| **REG-FE-074** | P2 conditional | An optional queue-settings network failure rejects `Promise.all` and hides otherwise successfully loaded doctor roster | **DORMANT / SOURCE-OBSERVED / REPRO-PENDING** |
| **REG-XC-001** | **P1 candidate, backend cross-contract** | Second price approval on an existing nonempty `Visit.doctor_price_override` uses in-place JSON mutation without SQLAlchemy dirty tracking | **BACKEND SOURCE-OBSERVED / DB-REPRO-PENDING**; API endpoint exists even if UI is dormant |

#### REG-FE-071 — `specialty` filter ignored

In [IntegratedDoctorSelector.tsx L29–41, L73–91, L167–183](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/registrar/IntegratedDoctorSelector.tsx#L29-L183), the component declares a `specialty` prop, calls `fetchRegistrarDoctors()` **without a specialty argument**, and renders `doctors.map` without filtering. `specialty` appears only in the empty-state label. Backend `/registrar/doctors` supports a specialty filter, and clinic policy separately enforces eligible doctor/service associations. If a future mounted consumer supplies `specialty="cardiology"`, dermatologists and dentists remain selectable despite the prop. This does not prove an unauthorized booking (backend policy remains authoritative).

**Red-first test (not run):** mount with synthetic doctor roster including cardio/derma/dental, `specialty="cardiology"`; assert only eligible matching records appear and only selected doctor IDs in canonical allowed scope can reach `onDoctorChange`. Retain server-side eligibility at save, do not substitute front-end specialty string as a policy decision.

#### REG-FE-072 — displayed queue range is not the doctor's actual ticket sequence

[IntegratedDoctorSelector.tsx L118–129, L226–237](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/registrar/IntegratedDoctorSelector.tsx#L118-L129) computes `start_number-(start_number+max_per_day-1)` from `queueSettings.specialties[doctor.specialty]` and labels it the doctor's **online queue**. The backend [`/registrar/queue-settings` L479–523](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/backend/app/api/v1/endpoints/registrar_integration/_queue_ops.py#L479-L523) explicitly returns a **specialty aggregate**, while the [`/registrar/doctors` L315–353](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/backend/app/api/v1/endpoints/registrar_integration/_services_doctors.py#L315-L353) includes doctor-specific `start_number_online` and `max_online_per_day`. Actual DailyQueue numbers are backend/day/owner scoped, including snapshot policy, and must not be fabricated from a general specialty configuration. The displayed hypothetical range may disagree with the individual doctor, and with already issued tickets. Reword as **specialty limit settings** or consume canonical doctor/day queue facts, never label range as issued/guaranteed ticket numbers.

**Red-first test:** doctors A and B share specialty but have different per-doctor limits; assert no fake per-doctor range from the shared specialty. Cover day with an already frozen queue snapshot.

#### REG-FE-073 — stale filter response can overwrite latest approval list

[PriceOverrideApproval.tsx L64–88](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/registrar/PriceOverrideApproval.tsx#L64-L88) defines `loadPriceOverrides` dependent on `statusFilter`; each response unconditionally calls `setPriceOverrides(data)` and `setLoading(false)`. Rapid filter change `pending → approved`, with deferred `pending` response resolving after the `approved` response, renders pending entries under the approved filter. The mutation handler [L90–115](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/registrar/PriceOverrideApproval.tsx#L90-L115) also calls `loadPriceOverrides()` without awaiting it or reconciling a stale response. Backend permissions and `available_actions` are correctly server-provided; this is a read-display freshness concern, not a proven authorization bypass.

**Red-first test:** render component with deferred `fetchPriceOverrides({statusFilter:'pending'})` A and approved B; resolve B then A; visible list and loading must belong to B. Repeat after approve/reject and immediately changing filter. Use request-epoch/abort guard; optimistic UI success remains gated to acknowledged command, but list refresh must not revert newer filters.

#### REG-FE-074 — optional settings failure blocks healthy doctor roster

[IntegratedDoctorSelector.tsx L73–101](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/registrar/IntegratedDoctorSelector.tsx#L73-L101) uses `Promise.all([fetchRegistrarDoctors(),fetchRegistrarQueueSettings()])` inside a single try/catch. If doctors succeeds but queue-settings fails 500/network, the component enters a global error state instead of showing doctors with queue metadata unavailable. This is an optional-display dependency blocking the primary selection surface. Backend read paths are independent. **Conditional dormant UI concern**.

**Red-first test:** doctor API resolves with valid roster, settings API rejects; doctor selection should remain available, queue range omitted, with a separate settings warning. A genuine doctors API failure must still not invent a roster.

#### REG-XC-001 — backend price approval can be acknowledged without persisting the visit override JSON (P1 candidate)

This is a **cross-contract finding in backend source** uncovered while reviewing `PriceOverrideApproval`; do **not** present it as a frontend production incident or ship it in this docs-only PR.

[Backend `_cart.py` L1314–1351](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/backend/app/api/v1/endpoints/registrar_wizard/_cart.py#L1314-L1351) sets the override `status="approved"`, then mutates `visit.doctor_price_override[str(service_id)]` in place. [Visit model L64](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/backend/app/models/visit.py#L64) maps this field as ordinary `mapped_column(JSON)` — **not `MutableDict`**. SQLAlchemy ordinarily does not detect in-place mutations to plain JSON-mapped dicts. For a **first** approval when JSON was empty, explicit `visit.doctor_price_override = {}` marks it changed; but for a **second** approval against a nonempty dict, there is no assignment/flag_modified, so the visit JSON may not be updated even though the DoctorPriceOverride record has an `approved` status and 2xx is returned. No `flag_modified` or explicit reassignment appears in this handler.

**DB red-first (not run):** create one Visit with price override for service A already persisted; create pending override for service B on same Visit; call the actual approval endpoint under Registrar; **open a new DB session** and assert both A and B are present in Visit JSON, B matches approved price and approval status is committed. A mock-only unit test cannot reveal ORM dirty tracking. Validate invoice/visit price invariants separately (do not claim amount changed in the financial ledger). Repair as canonical backend mutation (new dict assignment or correct tracking), with mandatory DB/financial/clinical policy gate before source edits.

### Positive checks and disposition

- `PriceOverrideApproval` *does* gate approve/reject UI actions by backend `available_actions` / `can_approve` / `can_reject`, failing closed when absent. Backend GET `/registrar/price-overrides` response explicitly includes these flags and `POST /registrar/price-override/approve` checks `Admin` or `Registrar` + pending state. No new RBAC-bypass claim is justified.
- `IntegratedDoctorSelector` schedule weekday order (Mon 0 → Sun 6) matches backend `ScheduleBase`; no weekday-offset bug found.
- `IntegratedServiceSelector` helper `getTotalPrice` is client-calculated demo/read-side display only; no consumer of this selector was found in live wizard. Avoid claiming production invoice corruption.
- Other unnumbered latent quality observations: `IntegratedDoctorSelector` uses a clickable `Card` with no keyboard/button semantics; `PriceOverrideApproval` requests only the latest 100 overrides, without pagination; do not inflate these into proven active user defects without route confirmation.
- State **SOURCE-OBSERVED / REPRO-PENDING** for all new candidates. No Vitest/pytest/Playwright/real payment requests and no SQLAlchemy session test were executed. A source-contract test for `PriceOverrideApproval` exists, but it checks action-gate string patterns, not mounted filter races or DB persistence.
- **Preferred owner decision before fixes:** If these components are intentionally retired, archive/remove legacy UI after import/build verification, with no need to turn them into production flows. If reactivation is planned, remove demo fallback, make date-aware server catalog and doctor ownership authoritative, and test the three components as mounted integrations. Backend REG-XC-001 should be triaged **independently**, because its endpoint remains reachable through HTTP even if the React UI is orphaned.


## Focused ModernDialog and EnhancedAppointmentsTable CSS/keyboard review (2026-11-02)

**Frozen source:** current `main 1595ce3dc907c64da57fd221de330646e4a9ed90`. Examined `frontend/src/components/dialogs/ModernDialog.tsx` (210 lines), `ModernDialog.css` (296 lines), `frontend/src/components/tables/EnhancedAppointmentsTable.tsx` (306 lines), `EnhancedAppointmentsTable.css` (976 lines). Followed real callers `AppointmentWizardV2.tsx`, `CancelDialog.tsx`, `PaymentDialog.tsx`, `PaymentProviderDialog.tsx`, `RescheduleSlots.tsx`, `RecordPreview.tsx`, `WorklistView.tsx`, table columns/state and canonical `DataTable.tsx`. Read available source-contract tests; no Playwright/browser execution. Compared against updated original registrar ledger #3803 `7fb79f340c8d174467ba05239bd498c0b271e4a0`.

**Deduplication boundary:** **Do not renumber** REG-FE-001 (Worklist row click logger-only), REG-FE-031 (selection without bulk action), REG-FE-043 (inline backend-action capability), REG-FE-049 (uncleared 100ms focus timer), REG-FE-050–055 (sorting/filter page/status/search/context-menu/row-key), REG-FE-057–060 (queue identity, render complexity, small viewport action menu, invalid `justify-content: between`). They remain in the prior audit with their own tests/fix owners. This pass identifies **different** underlying risks in the shared dialog/table CSS.

| ID | Priority candidate | Surface | Observation | Confidence |
| --- | --- | --- | --- | --- |
| **REG-FE-075** | **P2** | ModernDialog + active wizard | A modal composed with `customHeader` but without `title` has no accessible dialog name | **SOURCE-OBSERVED / REPRO-PENDING** |
| **REG-FE-076** | **P2** | ModernDialog focus trap | Selector counts disabled / hidden candidates as focusable; real CancelDialog action can be disabled while preceding button is last tabbable | **SOURCE-OBSERVED / REPRO-PENDING** |
| **REG-FE-077** | **P2** | Multiple ModernDialogs | Every open instance registers a global Escape/Tab handler, and each cleanup clears body overflow without stack ownership | **SOURCE-OBSERVED / REPRO-PENDING** |
| **REG-FE-078** | **P2** | EAT mobile toolbar + CSS | `min-width:600px` toolbar is inside EAT's clipped `overflow:hidden` ancestor; narrow screens can hide right-hand filters/export | **SOURCE-OBSERVED / BROWSER-REPRO-PENDING** |
| **REG-FE-079** | P3 | EAT CSS specificity | Broad `.enhanced-table div {color:... !important}` replaces semantic muted/warning colors for descendant `div` cells | **SOURCE-OBSERVED / VISUAL-REPRO-PENDING** |
| **REG-FE-080** | **P2** | ModernDialog close lifecycle | No capture/restore of the trigger element's focus; keyboard users can return to the page with focus dropped after modal close | **SOURCE-OBSERVED / REPRO-PENDING** |

### REG-FE-075 — Active wizard's `role=dialog` has no accessible name

**Evidence:** [ModernDialog.tsx L118–145](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/dialogs/ModernDialog.tsx#L118-L145) derives `aria-label` only when `customHeader && title` (and `title` is string), otherwise `aria-labelledby` only if `title` exists. [AppointmentWizardV2.tsx L3217–3231](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/wizard/AppointmentWizardV2.tsx#L3217-L3231) mounts the real registrar wizard with `customHeader={Step1Header|Step2Header}`, **no title**, and `isOpen`. Thus the wizard has `role="dialog" aria-modal="true"` and neither `aria-label` nor `aria-labelledby` from ModernDialog. A non-string custom title in a different callsite also yields undefined aria-label in the custom-header branch; a reusable modal should provide an explicit label/labelled-by contract.

**Fail-first (not run):** Mount the real wizard's `ModernDialog` composition (or a faithful customHeader-only fixture), inspect DOM and accessible name via `getByRole('dialog', {name: /.../})` plus axe; assert a nonempty, unique label for each active modal/step and avoid duplicate static `id="dialog-title"` when multiple dialogs mount. Repair with a required accessible title or explicit `aria-label` / `aria-labelledby` respecting custom header; do not rely on visual text alone.

### REG-FE-076 — Disabled action buttons can let Tab escape from an open modal

**Evidence:** [ModernDialog.tsx L61–84 and L89–96](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/dialogs/ModernDialog.tsx#L61-L96) queries `button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])` without filtering `:disabled`, `[hidden]`, `[inert]` or visibility. The query's final `:not` only modifies the last `[tabindex]` alternative, so *disabled buttons* remain in the NodeList. The wrap handler intercepts Tab only when `document.activeElement === lastElement`. In the live [CancelDialog.tsx L81–95](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/dialogs/CancelDialog.tsx#L81-L95), the final confirm button is disabled until a reason is entered, while preceding buttons/textarea are tabbable. Tab after the last enabled button therefore does not wrap and may exit the dialog or enter browser chrome.

**Fail-first:** Use RTL/userEvent or Playwright with CancelDialog, empty reason, last submit button disabled. Tab through close→textarea→cancel and assert focus remains inside modal and wraps to the first actually enabled, visible control. Include Shift+Tab, `showCloseButton=false`, a dialog with no tabbable controls, and inputs rendered with `disabled` after async request. Use robust focus trapping, not a selector that guesses visibility.

### REG-FE-077 — Multiple open dialogs independently handle Escape and incorrectly unlock body

**Evidence:** Each [ModernDialog.tsx L57–106](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/dialogs/ModernDialog.tsx#L57-L106) attaches a **document-level** keydown handler, sets `document.body.style.overflow='hidden'`, and on cleanup sets `overflow=''`. There is no topmost dialog coordination, refcount or previous style preservation. [PaymentProviderDialog.tsx L565–600](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/payment/PaymentProviderDialog.tsx#L565-L600) can render the main payment modal and an additional ticket-printer ModernDialog at once (`isOpen` plus `showTicketPrinter`), with main Escape enabled on success and nested Escape default enabled.

**Expected failure if nested branch is reached:** One Escape dispatches to both document listeners and invokes both onClose paths, potentially dismissing payment context as well as the topmost printer. If one modal closes while the other stays open, the first cleanup resets `body.style.overflow` and unlocks the background prematurely. Concurrent Tab handlers can also fight over focus; a pre-existing body overflow value is lost even in the one-modal case.

**Fail-first:** Two stacked ModernDialogs (including a PaymentProviderDialog `success` + ticket-printer synthetic fixture): assert one Escape only closes topmost, remaining modal still traps focus and locks body; after final close original overflow and trigger focus are restored. Avoid globally shared state that leaks across independent roots.

### REG-FE-078 — Under-600px toolbar can be clipped rather than scrollable

**Evidence:** [EnhancedAppointmentsTable.tsx L133–141 and L143–183](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/tables/EnhancedAppointmentsTable.tsx#L133-L183) wraps the entire component in `overflow:'hidden'` and renders the search, status filter and export toolbar inside. [EnhancedAppointmentsTable.css L669–683](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/tables/EnhancedAppointmentsTable.css#L669-L683) sets the **toolbar itself** to `min-width:600px; overflow-x:auto` with a nonwrapping flex inner. Under 600px parent width the toolbar's own minimum layout width exceeds the clipped container; its scrollport is also 600px wide, so controls positioned between parent width and 600px can be invisible/unreachable if inner content is not wide enough to scroll relative to that 600px box. The separate table body scrollbar does not fix toolbar reachability.

**Fail-first:** Playwright viewport widths 320, 375, 390, 568, 600, 768 px, registrar Worklist and shared Appointments page; assert search, filter and Export all visible or scroll-reachable without horizontal clipping, keyboard tab can scroll focused control into view. Fix by giving the *viewport-sized* toolbar scroll ownership or true responsive wrapping; do not change underlying row ID/status behaviors.

### REG-FE-079 — Force-primary descendant CSS defeats status/muted text colors

**Evidence:** [EnhancedAppointmentsTable.css L163–172](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/tables/EnhancedAppointmentsTable.css#L163-L172) applies `color: var(--mac-text-primary) !important` to **every descendant `div`**. CSS later styles `.eat-time-label`, `.eat-time-row`, `.eat-time-changed` as secondary/tertiary colors at [L786–809](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/tables/EnhancedAppointmentsTable.css#L786-L809), but without `!important`, so these are overridden. More importantly, [appointmentsTableColumns.tsx L1216–1234](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/tables/appointmentsTableColumns.tsx#L1216-L1234) uses an inline orange text color on a **div** payment-status badge. The broad stylesheet `!important` wins over the inline normal `color`, making partial/pending payment text the same primary color as ordinary text. Background can remain orange, so the loss of semantic hierarchy needs visual evaluation before calling this a serious readability defect.

**Fail-first:** Browser computed-style assertions for ordinary, stale/changed time, and `payment_status='partial'` rows in light+dark themes. Compare computed `color` to intended token and run contrast tests. Narrow the blanket descendant rule rather than adding more `!important` to individual status elements.

### REG-FE-080 — Closing an active modal does not restore keyboard focus

**Evidence:** [ModernDialog.tsx L55–106](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/dialogs/ModernDialog.tsx#L55-L106) sets focus into the modal (asynchronously, separately tracked as REG-FE-049) and removes key handler/overflow upon close, but **never captures the previously focused opening control** and never restores it. The component returns `null` when `isOpen=false` [L108](https://github.com/drsapaev/final/blob/1595ce3dc907c64da57fd221de330646e4a9ed90/frontend/src/components/dialogs/ModernDialog.tsx#L108). Removing the focused close/form button can leave `document.activeElement` on the body instead of the registrar's originating row/action trigger. This is independent from the already-recorded *uncancelled timer* REG-FE-049.

**Fail-first:** Keyboard-open `RecordPreview` or `CancelDialog` from a named table action, close via Escape/X/backdrop, assert focus returns to the original still-connected trigger; when trigger was removed by a successful mutation, restore to a sensible safe worklist fallback. Test nested dialogs with top-of-stack handoff.

### Source-positive findings / verification limits

- `EnhancedAppointmentsTable.tsx` already supplies `stickyHeader` and bounded `maxHeight=560` to canonical `DataTable`. Existing source-contract test checks these, and `DataTable` includes keyboard header sorting and `aria-sort`; no duplicate P2 on these controls.
- The row-action column does stop pointer propagation into row activation; report no new accidental row-action double command without a failing fixture.
- Prior REG-FE-051 search/page false-empty, REG-FE-049 focus timer, REG-FE-059 context-menu viewport overflow, REG-FE-060 invalid CSS justification, REG-FE-031 selection mismatch already have original tracking.
- This is source-level review only; **no** Vitest, axe, Playwright, browser visual screenshot, controlled staging, manual keyboard QA or production visit/payment action run in this PR. All severity P2/P3 is provisional. Do not claim a real patient was affected.
- Code remediation should use a **separate** implementation PR, maintain backend SSOT for action/queue/payment; shared dialog/table changes require broad synthetic consumers tests and the repo mandatory gate if crossing API/security/clinical queue flows. This Draft remains a documentation-only checkpoint.

## Validation and rollback

- Checked: prior audit indices, current repository `AGENTS.md`, project SSOT skill, canonical producer/consumer source and recent main commit via connected GitHub. Cross-checked the exact `refund_amount` name in both Pydantic and serializer; checked the actual `RecordPreview` consumer and `RefundType` enum.
- NOT run: local worktree state/PowerShell gate; Vitest/pytest/Playwright/axe; `git diff --check`; production or staging; CI for this newly created PR. Source review is **not a runtime test**.
- Rollback: revert this single Markdown commit or close the audit Draft. No data or application behavior changed.
- Stop: do not mark findings resolved or deploy until synthetic failing tests, mandatory domain gate for source fixes, independent review and successful required CI.
