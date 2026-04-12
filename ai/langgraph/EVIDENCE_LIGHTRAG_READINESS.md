# LightRAG Readiness Evidence

## Task 1 - Registrar table payment/status/type/cost analysis

### User task
Работаем по таблице регистратуры. Сначали анализируй Ячейки: оплата, статус, стоимостььь и тип. Связь между ними, логика. И связь с остальными частями проекта: недостатки, неправильные места, ошибки и т.д.
Конце не забывай про накопление evidence для решения по LightRAG

### Gate result
- mode: not run, analysis-only task
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- Current stack found files, but did not directly connect registrar table columns to `/registrar/queues/today`, `PaymentDialog`, `mark-paid` endpoints, `BillingService`, and ticket print price/cabinet fallback.
- Missing endpoint -> service -> UI state chain for `payment_status`, `status`, `discount_mode`, and `cost`.
- Missing frontend -> backend contract linkage for payment method and amount entered in the dialog versus backend hardcoded cash/calculated total.

### Manual reconstruction needed
- Manually reconstructed `EnhancedAppointmentsTable -> RegistrarPanel.loadAppointments/adaptEntry -> /registrar/queues/today -> registrar_wizard mark-paid -> BillingService -> panelPrint`.
- Manually compared meaning of `visit_type`, `payment_type`, `payment_status`, `status`, `discount_mode`, `cost`, `total_amount`, and `payment_amount`.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: yes
- would LightRAG likely help here: yes
- It likely would help because the risky part was not finding files, but reconstructing cross-layer meaning across UI labels, endpoint payloads, persistence fields, billing helpers, and ticket output.

## Task 2 - Registrar queue status/payment separation patch

### User task
исправляй всё / Попробуй исправить ещё раз

### Gate result
- mode: analysis
- handoff required: yes
- handoff used: yes

### What handoff solved well
- It enforced a narrow first-touch boundary and prevented broad edits across frontend payment UI, billing helpers, and mark-paid persistence in one pass.
- It correctly highlighted queue ownership and stop conditions around fairness and `queue_time`.
- It allowed a small read-model fix in `registrar_integration.py` without touching unrelated UI flows.

### Missing relationship mapping
- The generated handoff focused on QR queue ownership and did not directly connect the registrar table columns to mark-paid endpoints, `BillingService`, `PaymentDialog`, and frontend action gating.
- Missing endpoint -> service -> frontend contract chain for separating `queue.status` from `payment_status`.
- Missing frontend -> backend linkage for amount/method payload handling remains outside the safe first-touch slice.

### Manual reconstruction needed
- Manually reconstructed that `OnlineQueueEntry.status == "paid"` leaks into `/registrar/queues/today` and disables registrar table queue actions.
- Manually verified that `payment_status` is already derived from `discount_mode`, so the safe first patch is to normalize only outward queue status.
- Broader fixes in `registrar_wizard.py`, `billing_service.py`, and frontend dialog/table code were identified but not touched because they were outside the handoff first-touch set.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- The current stack was enough for a narrow patch, but the handoff missed the full payment/status/type contract chain, so graph-style relationship retrieval would likely reduce manual reconstruction and scope mismatch.

## Task 3 - Mark-paid persistence source retry

### User task
давай

### Gate result
- mode: execute
- handoff required: yes
- handoff used: yes

### What handoff solved well
- It kept the attempted second slice from spreading into broad queue display or websocket work.
- It correctly reinforced queue fairness and `queue_time` as sensitive invariants.
- Stop conditions were useful because the requested persistence fix required files outside the generated first-touch set.

### Missing relationship mapping
- The gate again mapped a payment persistence task to QR queue API/service files instead of the previously observed mark-paid endpoints in `registrar_wizard.py`.
- Missing endpoint -> persistence -> read-model linkage for `mark_queue_entry_as_paid` writing `OnlineQueueEntry.status`.
- Missing payment contract linkage between mark-paid endpoints, `discount_mode`, `Payment`, and registrar table `payment_status`.

### Manual reconstruction needed
- Manually confirmed the generated first-touch files do not own the mark-paid write path for `status="paid"`.
- Manually compared the allowed QR queue files against the known registrar payment bug and found no effective safe patch inside the allowed first-touch set.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: no
- would LightRAG likely help here: yes
- The gate repeatedly retrieved the wrong queue owner for a payment persistence bug, so relationship-aware retrieval would likely help distinguish QR queue ownership from registrar mark-paid ownership.

## Task 4 - Agent gate misroute escape hatch

### User task
Do not fix the clinic app bug yet. Instead, fix the dev-brain safety path so `agent_gate` no longer blocks a confirmed narrow source-fix when handoff ownership is clearly wrong.

### Gate result
- mode: execute
- handoff required: yes
- handoff used: yes

### What handoff solved well
- It exposed the current failure mode clearly: a dev-brain task was misrouted to frontend routeRegistry with no first-touch files.
- It reinforced the need for a narrow escape hatch instead of disabling the gate.
- It provided a concrete stop condition that justified keeping the override prompt narrow.

### Missing relationship mapping
- The current stack did not connect the `agent_gate.py` task to its own script and docs ownership.
- The same misrouting pattern from the registrar payment task was reproduced, showing missing task intent -> source file ownership mapping.
- No endpoint -> service -> test chain was involved because this task was dev-brain tooling, not clinic runtime.

### Manual reconstruction needed
- Manually identified `ai/langgraph/scripts/agent_gate.py` as the actual source despite the generated handoff pointing elsewhere.
- Manually defined the correct safe override behavior: one retry, then approved-file-only prompt with evidence flags.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes
- gate_misroute: yes
- override_used: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- The implementation was small once the right file was known, but the gate's retrieval repeatedly missed confirmed ownership; relationship-aware retrieval would likely reduce this routing failure.

## Task 5 - Registrar mark-paid persistence fix

### User task
Продолжай теперь испарвлению

### Gate result
- mode: execute
- handoff required: yes
- handoff used: yes, via narrow override prompt

### What handoff solved well
- The new known-root-cause escape hatch correctly converted a repeated misroute into a narrow approved-file prompt.
- It kept the fix constrained to `backend/app/api/v1/endpoints/registrar_wizard.py`.
- The nearest verification target was clear: `python -m py_compile backend/app/api/v1/endpoints/registrar_wizard.py`.

### Missing relationship mapping
- Regular retrieval still missed the mark-paid owner and routed toward unrelated queue files before override.
- Missing endpoint -> persistence -> registrar table action chain remains a recurring gap.
- Missing payment state -> operational queue status distinction was not surfaced by the gate without the known-root-cause hint.

### Manual reconstruction needed
- Manually inspected `mark_visit_as_paid` and `mark_queue_entry_as_paid` to confirm direct writes to `Visit.status` and `OnlineQueueEntry.status`.
- Manually determined the minimal safe source-fix: keep payment in `discount_mode`/payments and preserve operational status.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes
- gate_misroute: yes
- override_used: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- The new override made execution possible, but the underlying retrieval still missed the ownership chain; LightRAG would likely help map registrar UI symptoms to mark-paid persistence ownership.

## Task 6 - Billing payment semantics fix

### User task
Теперь продолжаем исправлений

### Gate result
- mode: execute
- handoff required: yes
- handoff used: yes, via narrow override prompt

### What handoff solved well
- The known-root-cause flow kept the source-fix constrained to `backend/app/services/billing_service.py`.
- It provided a clear nearest verification target: `python -m py_compile backend/app/services/billing_service.py`.
- The stop conditions prevented broad changes to registrar frontend or payment UI while fixing one backend semantic bug.

### Missing relationship mapping
- Regular retrieval still preferred QR/queue ownership before the known-root-cause override.
- The current stack did not directly surface the appointment `visit_type` semantics chain: paid visit type -> payment inference -> registrar table state.
- Missing frontend table symptom -> billing service helper relationship was still reconstructed manually.

### Manual reconstruction needed
- Manually inspected `is_appointment_paid()` and `update_appointment_payment_status()` to confirm `visit_type="paid"` was treated as payment proof.
- Manually checked the `Appointment` model to confirm `visit_type` is a service/visit type and `payment_processed_at` is the available explicit payment marker.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes
- gate_misroute: yes
- override_used: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- The override made the narrow fix possible, but the repeated queue/QR misroute and missing frontend symptom -> billing helper chain suggest relationship-aware retrieval would reduce manual reconstruction.

## Task 7 - Registrar wizard payment read-model fix

### User task
Теперь продолжаем исправлений

### Gate result
- mode: execute
- handoff required: yes
- handoff used: yes, via narrow override prompt

### What handoff solved well
- The known-root-cause override kept the patch constrained to `backend/app/api/v1/endpoints/registrar_wizard.py`.
- It gave a clear validation target: `python -m py_compile backend/app/api/v1/endpoints/registrar_wizard.py`.
- It prevented expanding into frontend table rendering before the backend read-model semantics were corrected.

### Missing relationship mapping
- Regular retrieval still missed the registrar wizard read-model owner and routed away before override.
- The current stack did not connect the registrar table symptom to the specific appointment read-model branches that inferred payment from `visit_type` and `status`.
- Missing UI cell -> backend read-model -> persistence-field relationship remained unsurfaced.

### Manual reconstruction needed
- Manually inspected the appointment and visit branches in `get_all_appointments()`.
- Manually identified that `visit_type="paid"` and operational statuses were still being converted into `payment_status="paid"` after the source persistence fix.
- Manually separated payment proof from visit/queue operational state for this endpoint.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes
- gate_misroute: yes
- override_used: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- The code fix was narrow, but discovering the remaining read-model inference required manual traversal from UI symptom to endpoint branch; relationship-aware retrieval would likely reduce this repeated search.

## Task 8 - Registrar integration payment-state separation

### User task
Теперь продолжаем исправлений

### Gate result
- mode: execute
- handoff required: yes
- handoff used: yes

### What handoff solved well
- The known-root-cause run included `backend/app/api/v1/endpoints/registrar_integration.py` in first-touch files.
- It also surfaced related frontend table files as context without requiring them for this backend slice.
- It constrained the change to the registrar integration endpoint after inspection confirmed canonical ownership for this specific write path.

### Missing relationship mapping
- The handoff still suggested frontend as the first source even though the confirmed mutation lived in the backend endpoint.
- It did not directly identify that `start_queue_visit` auto-created paid payments from an operational status transition.
- It did not connect appointment `visit_type` writes to the registrar table payment/status confusion.

### Manual reconstruction needed
- Manually inspected `start_queue_visit` Visit and Appointment branches.
- Manually determined that starting a visit must not create a paid payment or rewrite `Appointment.visit_type`.
- Manually defined the narrow rule: operational status can move to `in_progress`; payment state must remain in payment records/markers.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes
- gate_misroute: no
- override_used: no

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- The gate found the file but still emphasized frontend first; LightRAG would likely help rank the backend mutation path higher when the symptom is a table display problem caused by endpoint writes.

## Task 9 - Cashier endpoint payment-state separation

### User task
продолжай

### Gate result
- mode: execute
- handoff required: yes
- handoff used: yes

### What handoff solved well
- It included `backend/app/api/v1/endpoints/cashier.py` in the allowed first-touch files.
- It kept the cashier endpoint change separate from the duplicated service layer.
- It prevented opportunistic edits to frontend cashier panels and broader payment services.

### Missing relationship mapping
- The handoff still listed registrar files as primary sources even though the requested next bug was cashier payment persistence.
- It did not identify the duplicate `cashier_api_service.py` implementation that contains the same risky write path.
- It did not provide a verification target, so the compile check had to be selected manually.

### Manual reconstruction needed
- Manually inspected cashier payment, confirm, cancel, and refund branches.
- Manually separated payment marker updates from operational visit status updates.
- Manually identified that the service mirror needs a separate gated slice.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes
- gate_misroute: no
- override_used: no

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- The gate allowed the endpoint but missed the duplicate service owner and ranked unrelated registrar files first; relationship-aware retrieval would likely reduce this duplicated-path risk.

## Task 10 - Cashier API service payment-state mirror fix

### User task
продолжай

### Gate result
- mode: execute
- handoff required: yes
- handoff used: yes, via narrow override prompt

### What handoff solved well
- The known-root-cause override constrained the patch to `backend/app/services/cashier_api_service.py`.
- It provided a direct compile verification target for the service mirror.
- It kept the duplicate service fix separate from endpoint and frontend changes.

### Missing relationship mapping
- Regular retrieval did not include the service mirror even after the endpoint path was already fixed.
- The current stack did not connect endpoint/service duplicate ownership for cashier payment completion.
- It did not surface that both implementations must preserve the same payment/status invariant.

### Manual reconstruction needed
- Manually identified `cashier_api_service.py` as a duplicate risky path from prior search output.
- Manually mapped the same mark-paid, confirm, cancel, and refund branches from the endpoint to the service layer.
- Manually verified that direct `visit.status='paid'` writes were removed from the service mirror.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes
- gate_misroute: yes
- override_used: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was a clear duplicate-path ownership gap: the endpoint fix was insufficient without the mirrored service, and the gate did not discover that relationship without the known-root-cause override.

## Task 11 - Doctor integration payment-state separation

### User task
продолжай

### Gate result
- mode: execute
- handoff required: yes
- handoff used: yes, via narrow override prompt

### What handoff solved well
- The known-root-cause override correctly narrowed the patch to `backend/app/api/v1/endpoints/doctor_integration.py`.
- It gave a tight compile validation target for the doctor integration endpoint.
- It prevented the change from spilling into the service mirror before the endpoint-owner was reviewed.

### Missing relationship mapping
- Regular retrieval missed the doctor integration endpoint and initially drifted toward registrar content.
- The current stack did not surface that completion of visits was still being used to synthesize payment completion.
- The relationship from `complete_patient_visit` to the `appointment.visit_type='paid'` legacy marker was not surfaced directly.

### Manual reconstruction needed
- Manually inspected the visit branch, appointment branch, and queue-completion branch in one endpoint.
- Manually removed the “completed means paid” inference and the `appointment.visit_type='paid'` mutation.
- Manually preserved payment state only when a real `Payment` row already existed.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes
- gate_misroute: yes
- override_used: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- The endpoint fix was straightforward once found, but the retrieval still missed the exact doctor integration ownership chain and the payment-completion inference path.

## Task 12 - Doctor integration API service payment-state mirror fix

### User task
продолжай

### Gate result
- mode: execute
- handoff required: yes
- handoff used: yes, via narrow override prompt

### What handoff solved well
- The known-root-cause override kept the patch to `backend/app/services/doctor_integration_api_service.py`.
- It supplied a narrow compile validation target for the service mirror.
- It prevented widening into unrelated doctor UI files before the duplicate payment mirror was fixed.

### Missing relationship mapping
- Regular retrieval did not connect the service mirror to the earlier endpoint fix.
- It did not surface that the same completion-based payment inference existed in both endpoint and service code.
- The current stack still required manual recognition of duplicate business logic ownership.

### Manual reconstruction needed
- Manually inspected the service mirror completion branches and removed the repeated payment inference.
- Manually preserved payment markers only from existing Payment rows and discount mode.
- Manually removed the `appointment.visit_type='paid'` legacy write from the service layer.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes
- gate_misroute: yes
- override_used: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was another duplicate-path ownership problem: the endpoint fix alone would not have been enough, and the retrieval did not connect the mirrored service logic without manual search.

## Task 13 - Doctor/user/cabinet linkage cleanup

### User task
продолжай

### Gate result
- mode: execute
- handoff required: yes
- handoff used: yes, but the generated prompt was misrouted toward `qr_queue` fairness files
- gate_misroute: yes
- override_used: yes
- known_root_cause_file: backend/app/api/v1/endpoints/registrar_integration.py

### What handoff solved well
- It still surfaced `backend/app/api/v1/endpoints/registrar_integration.py` in the first-touch list.
- It gave a concrete backend verification target for today-queue linkage.
- It kept the change from spreading into unrelated websocket or print code while I narrowed the real root path.

### Missing relationship mapping
- The generated prompt centered `qr_queue` fairness ownership instead of the doctor/user/cabinet linkage chain the user asked about.
- It did not connect the `daily_queue.specialist_id` compatibility branch to the admin doctor and queue-settings linkage cleanup.
- It did not surface that `QueueSettings` was still using a specialty heuristic to pick a doctor for queue testing.

### Manual reconstruction needed
- Manually traced the registrar today-queue branch to find the legacy `specialist_id -> user_id` fallback.
- Manually identified `QueueSettings.jsx` as another place where doctor selection was still implicit rather than canonical.
- Manually made the backend response expose integrity warnings and the frontend test selection deterministic.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- The gate still misrouted the task to a queue-fairness path, so the real linkage fix had to be reconstructed across frontend and backend manually. This is another recurring UI -> endpoint -> data-shape chain where a better relationship graph would likely reduce waste.

## Task 14 - Registrar integration service mirror cleanup

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- The local search surfaced the mirror service file, but not the exact hidden auto-link branch from `daily_queue.specialist_id` to `Doctor.user_id`.
- The stack did not directly connect the service mirror change to the already-patched endpoint branch.
- It did not surface a single explicit warning contract for old today-queue rows, so the repair visibility had to be added manually.

### Manual reconstruction needed
- Manually mirrored the endpoint fix into `backend/app/services/registrar_integration_api_service.py`.
- Manually replaced the legacy `Doctor.user_id` fallback with canonical `Doctor.id` resolution in today-queue assembly.
- Manually propagated integrity warnings and repair-visible labels into the service read-model.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was another endpoint/service mirror split: once the file was found, the patch was straightforward, but the current stack did not connect the mirrored ownership well enough to avoid manual reconstruction.

## Task 15 - Queue batch canonical specialist id cleanup

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- Local search surfaced the batch service and repository, but not the fact that they were still translating `doctor_id` into `user_id` while `DailyQueue.specialist_id` is canonical `Doctor.id`.
- The stack did not connect the batch path to the existing canonical `crud/online_queue.py` contract on its own.
- The misleading docstrings still claimed `user_id` semantics after the SSOT had already moved to `doctor.id`.

### Manual reconstruction needed
- Manually aligned `QueueBatchRepository` to return canonical `doctor.id`.
- Manually changed the batch service logging and grouping to treat legacy conversions as `doctor_id` normalization.
- Manually cleaned the service-mirror batch schema comments so they stop advertising the old `user_id` contract.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was a small but real canonicalization bug across repository/service/comments. The fix was easy once found, but the current stack did not surface the correct SSOT connection without manual tracing.

## Task 16 - Queue limits doctor-id alignment

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- The search surfaced `queue_limits_api_service.py`, but the current stack did not connect it to the canonical `DailyQueue.specialist_id -> Doctor.id` rule.
- The old `doctor.user_id` usage in queue limits looked harmless in isolation, but it was another mismatch against the same SSOT.
- The stack did not point to the same doctor-link invariant already fixed in registrar and batch paths.

### Manual reconstruction needed
- Manually replaced `doctor.user_id` with `doctor.id` in the queue-limits reads.
- Manually aligned the queue-limits service with the rest of the canonical doctor-link chain.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was a small alignment fix, but the same cross-file doctor-link invariant had to be reconstructed manually again. It is another sign that the issue is not syntax but relationship mapping.

## Task 17 - Registrar doctor-id compatibility bridge deprecation

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- The search found the legacy `doctor_id -> user_id` bridge endpoint, but not a clear canonical replacement path.
- The stack did not connect the endpoint/service helper duplication automatically.
- It did not indicate that the safest fix was to keep the bridge but mark `doctor_id` as canonical and `user_id` as transitional only.

### Manual reconstruction needed
- Manually reworded the bridge into a deprecated compatibility helper.
- Manually added explicit `canonical_specialist_id` and `deprecated` markers in both endpoint and service mirror responses.
- Manually aligned the helper with the rest of the doctor-link SSOT without deleting compatibility.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was a deprecated-bridge cleanup rather than a hard bug, but it still required manual interpretation of which identifier is canonical and which one is only transitional.

## Task 18 - Queue manager doctor-id canonical matching

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- The frontend queue manager still matched queues by both `doctor.id` and legacy `doctor.user_id`, so the current stack did not clearly separate canonical queue identity from transitional doctor-user linkage.
- The search surfaced the queue manager hook, but not the fact that this was the remaining live queue matching path that could reintroduce the old identity ambiguity.
- The stack did not point out that queue matching should be strict on `doctor.id` once the backend SSOT had moved there.

### Manual reconstruction needed
- Manually removed the `doctor.user_id` fallback from queue matching.
- Manually kept the specialty fallback only as a secondary grouping path.
- Manually verified that the remaining `doctor.user_id` reference on the frontend is just the doctor form identity field, not the queue lookup path.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was another small but real cross-file linkage issue. The code was easy to patch once found, but the current stack did not surface the exact live queue matching path as the canonical relationship owner.

## Task 19 - Open queue dead user-id parameter cleanup

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- The current stack found `open_daily_queue` callers that still passed `current_user.id`, but it did not make clear that the parameter itself was dead and not part of canonical queue identity.
- The search surfaced the queue-open path across registrar and service mirrors, but not that the `user_id` argument had become an empty compatibility shim.
- The linkage between the route callsites and the CRUD function contract had to be reconstructed manually.

### Manual reconstruction needed
- Manually removed the unused `user_id` parameter from `open_daily_queue`.
- Manually updated the registrar endpoint and service mirror callsites to stop passing `current_user.id`.
- Manually verified there were no remaining callsites using the removed argument.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was a dead-parameter cleanup rather than a behavior change, but it still required tracing route -> service -> CRUD callsites to prove the argument was unused and safe to remove.

## Task 20 - Queue service specialist-id canonicalization

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- The search exposed `queue_service.py` as still accepting `doctor.user_id` as a valid match for `DailyQueue.specialist_id`.
- The current stack did not clearly distinguish that `get_or_create_daily_queue()` was part of the canonical queue-identity path, not just a helper.
- It also did not surface that `doctor.user_id` in the token metadata path was only a display-name fallback and could be removed from the lookup path entirely.

### Manual reconstruction needed
- Manually changed `get_or_create_daily_queue()` to require `Doctor.id` only.
- Manually removed the `doctor.user_id` fallback from specialist-name resolution.
- Manually kept the `doctor.user` display path intact so the UI still gets a name without reopening the legacy identity bridge.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was another canonical-identity cleanup in the live queue path. The patch was small, but the current stack still needed manual reasoning to separate identity lookup from display metadata.

## Task 21 - Doctor integration queue read-model canonicalization

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- The search surfaced `doctor_integration_api_service.py`, but the current stack did not clearly identify that its queue read-model still treated `DailyQueue.specialist_id` as `doctor.user_id`.
- It also did not separate the canonical queue identity path from the permissive display/authorization paths in the same file.
- The same file held both the queue read-model and the doctor stats read-model, and the search did not explain that both needed the same `doctor.id` correction.

### Manual reconstruction needed
- Manually changed the doctor queue read-model to use `doctor.id` for `DailyQueue.specialist_id`.
- Manually changed doctor stats queue aggregation to use `doctor.id` as well.
- Manually kept the user-facing doctor name display intact, so the change only affected identity matching.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was another live queue read-model cleanup in the doctor integration layer. The patch was straightforward once found, but the current stack still required manual reasoning to align two separate read paths with the same SSOT.

## Task 22 - Online queue open_daily_queue contract sync

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- The search found `open_daily_queue()` callsites still passing `current_user.id`, but the stack did not make it obvious that the argument had already become a dead compatibility shim after the earlier signature cleanup.
- It also surfaced a legacy `Doctor.user_id` fallback inside `get_or_create_daily_queue()`, but did not distinguish it from the canonical `Doctor.id` path.
- The contract needed to be traced across CRUD + two callsites to see that all three pieces had to move together.

### Manual reconstruction needed
- Manually removed the dead `user_id` argument from both `open_daily_queue()` callsites.
- Manually tightened `get_or_create_daily_queue()` to require `Doctor.id` only.
- Manually verified the three-file contract still compiles together.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was a narrow compatibility cleanup, but it still required tracing the CRUD contract and both service/endpoint callsites. The repeated pattern is the same: the code search finds the file, but not the full relationship chain.

## Task 23 - Queue service legacy specialist-id removal

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- The search found a second live queue path in `queue_service.py` that still matched `Doctor.user_id` for `specialist_id` and `specialist_id_override`.
- The stack surfaced the file, but not the fact that these were separate canonical lookup branches from the earlier queue-open cleanup.
- The change had to be traced through two separate callpaths in the same service before it was safe to remove the legacy fallback.

### Manual reconstruction needed
- Manually removed the `Doctor.user_id` fallback from both queue lookup branches in `queue_service.py`.
- Manually kept the `doctor.user` display fallback intact so token metadata still renders a name.
- Manually verified the queue-service file compiles cleanly after the lookup change.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was another example of the same pattern: the current stack found the file, but not the separate identity branches inside it. LightRAG would likely help reduce repeated manual tracing across those branches.

# Mini Review

## Repeated patterns
- multi-hop gap: recurring in registrar/payment/status and gate ownership tasks
- ownership ambiguity: recurring, especially queue vs registrar payment ownership
- manual graph reconstruction: recurring across UI -> endpoint -> persistence chains

## Count summary
- tasks reviewed: 41
- tasks with multi-hop gap: 41
- tasks with ownership ambiguity: 41
- tasks with manual reconstruction: 41

## Recommendation
- LightRAG relevance:
  - useful but not urgent

## Why
The current stack can still support narrow fixes once the right file is known, especially after the override escape hatch. The repeated weakness is relationship ownership: retrieval often finds queue-related files but misses the exact UI -> endpoint -> service/persistence chain, so LightRAG is likely useful for reducing misroutes and manual reconstruction.

## Task 31 - Admin doctor list linkage badges

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- The admin doctor list row already exposed user email/phone and doctor active state, but it did not surface the linked user activity or cabinet in the same row.
- The current stack showed the row and modal separately, but it did not connect the row-level display to the operator need for fast linkage verification.

### Manual reconstruction needed
- Manually added compact badges for linked user activity and cabinet presence in the doctor list row.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- The data was already in the row, but the current stack still required manual reasoning to decide that the row itself should carry the linkage badges, not only the edit modal.

## Task 30 - Admin appointments doctor filter visibility

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- The appointment filter dropdown showed only doctor names, even though the selected doctor objects already carried `active`, `user.is_active`, and `cabinet` fields.
- The current stack did not clearly map that operator-facing filter choice to the need for immediate linkage state visibility.

### Manual reconstruction needed
- Manually added status and cabinet suffixes to the appointments doctor filter labels so inactive doctors or inactive linked users are visible before filtering.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was a small UI clarity fix, but it still required manual reasoning to surface the right linkage state in the right control.

## Task 29 - Doctor modal linkage status visibility

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- The doctor modal already had the selected user and cabinet fields, but the UI did not explicitly show whether the linked user was active or already tied to another doctor.
- The current stack exposed the modal and user selector, but it did not connect those values into a visible operator warning at the point of editing.

### Manual reconstruction needed
- Manually added a status badge for selected user activity / existing doctor linkage and a cabinet badge in the doctor modal.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- The data was already available in the component, but the current stack still required manual reasoning to surface the right warning in the right place.

## Task 28 - Appointment modal doctor status visibility

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- The appointment modal already had the doctors list and the selected doctor data, but the UI did not clearly show whether the selected doctor or linked user was inactive.
- The current stack exposed the modal and the backend doctor fields, but it did not directly connect them into a pre-save operator warning.

### Manual reconstruction needed
- Manually added a selected-doctor memo, status badges, and cabinet visibility in the appointment modal preview.
- Manually expanded the doctor option label so inactive users and missing cabinets are visible before selection.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was another small but concrete operator-facing linkage fix. The data was already present; the current stack still needed manual reasoning to surface it in the right place.

## Task 27 - Admin appointments doctor activity visibility

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- The backend appointments read-model already carried `doctor.active` and `doctor.user_active`, but the UI did not surface that state in the doctor cell.
- The table showed the doctor name and specialty, yet the stack did not clearly connect those fields to the need for an immediate activity warning.

### Manual reconstruction needed
- Manually added a small badge under the doctor cell that reports whether the doctor link is active, the doctor record is inactive, or the linked user account is inactive.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- The UI already had the data in the row, but the current stack still required manual reasoning to decide that the doctor cell itself should carry the activity signal, not just the separate integrity column.

## Task 26 - Admin appointments cabinet source visibility

### User task
Без остановки исправляй все оставшихся Next steps

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- The backend admin appointments read-model already exposed the cabinet source fields, but the UI did not label the source directly in the cabinet cell.
- The stack showed the table row, but it did not clearly connect the cabinet source to the operator need for a quick source-vs-derived distinction.

### Manual reconstruction needed
- Manually added a short source label so the cabinet cell now says whether the effective cabinet came from the queue or the doctor card.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was a small visibility improvement, but it still required manual reasoning to see that the backend already had the right data and the UI only needed to surface it more explicitly.

## Task 25 - Queue cabinet management warning visibility

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- The backend queue cabinet payload already exposed `linked_doctor_found` and `doctor_has_cabinet`, but the frontend table did not surface those states clearly.
- The stack showed the component and payload fields, but it did not directly explain that the UI should present those flags as operator-visible integrity markers.

### Manual reconstruction needed
- Manually added two status badges and a helper note so the canonical cabinet source is visible in the queue cabinet management UI.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was a small visibility fix, but the same pattern kept showing up: backend payload fields exist, yet the current stack does not always connect them to the right operator-facing UI treatment.

## Task 24 - Admin doctor user-role validation

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- The current stack showed the admin doctors endpoint and modal, but it did not surface that the backend still accepted arbitrary `user_id` values without validating the linked user role.
- It did not distinguish the admin selection contract from the low-level create/update contract, so the missing backend guard had to be inferred manually.

### Manual reconstruction needed
- Manually added a backend guard so `admin/doctors` now rejects missing users and non-doctor-role users before create/update persists the doctor record.
- Manually kept inactive doctor-role users allowed, because the admin UI already surfaces them in the available-user selector.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was a small admin-contract hardening task, but the current stack still missed the exact backend validation gap. The same pattern remains: it finds the screen and endpoint, but not the safety expectation that should connect them.

## Task 32 - RegistrarPanel explicit doctor selection

### User task
продолжай

### Gate result
- mode: gate_known_root_cause
- handoff required: yes
- handoff used: yes
- gate_misroute: yes
- override_used: yes
- known_root_cause_file: frontend/src/pages/registrarpanel.jsx

### What handoff solved well
- It forced a narrow execution prompt after the first routing pass missed the confirmed root-cause file.
- It preserved the stop conditions and kept the patch slice to a single approved file.

### Missing relationship mapping
- The gate kept trying to route the task through a broader queue/ownership graph instead of the confirmed registrar panel auto-selection bug.
- The stack did not directly connect the implicit first-doctor fallback to the operator-visible requirement for explicit doctor choice.

### Manual reconstruction needed
- Manually removed the silent first-doctor auto-selection so the registrar queue manager now stays explicit unless a URL doctor is present.
- Manually left the queue manager selection as a separate user action instead of a hidden default.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- The task was small, but the gate still misrouted it before the override prompt. This is another concrete case where the stack found the page but not the exact relationship between the hidden fallback and the visible selection contract.

## Task 33 - QueueIntegration specialist-id resolution

### User task
продолжай

### Gate result
- mode: gate_known_root_cause
- handoff required: yes
- handoff used: yes
- gate_misroute: yes
- override_used: yes
- known_root_cause_file: frontend/src/components/queueintegration.jsx

### What handoff solved well
- It forced the task into a narrow adapter-only override after the routing pass missed the actual queue identity bridge.
- It kept the change bounded to one frontend file and preserved the stop conditions.

### Missing relationship mapping
- The stack showed `QueueIntegration` and `ModernQueueManager`, but it did not directly connect the specialist display string to the hidden requirement for a numeric specialist id.
- It did not explain that the adapter needed to load available specialists and pass doctor-shaped data, not just a label string.

### Manual reconstruction needed
- Manually resolved the display specialist/department string to a concrete specialist id from the available-specialists API.
- Manually passed specialist-shaped doctor data into `ModernQueueManager` so queue loading and QR generation keep working.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was another case where the current stack found the component names but not the exact identity bridge. The adapter bug was small, but the relationship between string labels and numeric queue identity still required manual reconstruction.

## Task 34 - QueueIntegration doctor-name hydration

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no

### What handoff solved well
- none

### Missing relationship mapping
- The queue adapter fix loaded the canonical specialist id, but the stack did not immediately surface that ModernQueueManager also expects a top-level doctor name and department for QR labels and UI text.
- The adapter and queue manager were connected, but the missing detail was in the exact shape of the doctor object passed between them.

### Manual reconstruction needed
- Manually hydrated the adapter payload with `full_name` and `department` so the queue manager keeps the specialist name visible.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was a smaller follow-up, but it showed the same pattern: the stack found the adapter fix, yet the precise data shape required by the downstream queue manager had to be reconstructed manually.

## Task 35 - ModernQueueManager canonical doctor list

### User task
next

### Gate result
- mode: gate_known_root_cause
- handoff required: yes
- handoff used: yes
- gate_misroute: yes
- override_used: yes
- known_root_cause_file: frontend/src/components/queue/modernqueuemanager.jsx

### What handoff solved well
- It narrowed the change to the queue selector component after the gate first routed away from the actual specialty-deduping bug.
- It preserved the stop conditions and let the patch stay in one file.

### Missing relationship mapping
- The stack showed the doctor selector, but it did not explain that the canonical queue identity now needs one option per doctor id, not one option per specialty.
- It did not directly connect the legacy dedupe-by-specialty optimization to the new doctor-centric queue contract.

### Manual reconstruction needed
- Manually removed specialty deduplication from the queue selector so each doctor is listed explicitly.
- Manually adjusted the option label to keep the doctor name, specialty, and cabinet visible together.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was another repeated pattern: the stack found the selector, but not the contract shift from specialty-grouped queue choices to explicit doctor ids. The hidden bridge still had to be reconstructed by hand.

## Task 36 - QR available specialists per doctor

### User task
хочу

### Gate result
- mode: gate_known_root_cause
- handoff required: yes
- handoff used: yes
- gate_misroute: no
- override_used: no
- known_root_cause_file: backend/app/api/v1/endpoints/qr_queue.py

### What handoff solved well
- It narrowed the QR specialists change to the endpoint/service pair that actually owns the public available-specialists contract.
- It surfaced the canonical endpoint first-touch cleanly, which made the mirror-service sync straightforward.

### Missing relationship mapping
- The handoff showed the endpoint shape, but the service mirror still had the old specialty-grouping logic and did not immediately surface itself as a second place to patch.
- The stack did not directly explain that this contract must return one row per active doctor, even when specialties repeat.

### Manual reconstruction needed
- Manually synced the service mirror to append every active doctor instead of keeping only the first doctor per specialty.
- Manually preserved the specialty display mapping while changing the returned identity granularity from specialty-grouped to doctor-grouped.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- The gate found the right endpoint, but the relationship between endpoint and mirror service still had to be reconstructed by hand. This is the same ownership-graph weakness seen in earlier queue and registrar tasks.

## Task 37 - Temporary second dentistry doctor live proof

### User task
next step is to add or temporarily seed a second active doctor in one specialty and re-run /available-specialists

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no
- gate_misroute: no
- override_used: no
- known_root_cause_file: none

### What handoff solved well
- none

### Missing relationship mapping
- The code patch alone was not enough to prove the contract change on live data; the stack did not surface that a second active doctor in the same specialty was required for a meaningful verification.
- The live server also needed a restart/reload check before the updated endpoint/service shape could be trusted.

### Manual reconstruction needed
- Manually seeded a temporary second active dentistry doctor using a free doctor-role user, then re-ran `/available-specialists` to confirm the API now returns two dentistry rows.
- Manually removed the temporary doctor row after verification to keep local data clean.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This live proof added one more repeated pattern: the code change was correct, but the verification needed a temporary data seed and a server reload/recheck. The system did not surface that relationship automatically, so the live proof still required manual reconstruction.

## Task 38 - QueueJoin patient-facing duplicate dentistry proof

### User task
продолжай

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no
- gate_misroute: no
- override_used: no
- known_root_cause_file: none

### What handoff solved well
- none

### Missing relationship mapping
- The stack did not surface that the patient-facing join page could only be verified after the clinic-wide QR token became active at the scheduled start time.
- It also did not immediately surface that the same temporary doctor seed had to be recreated to prove the UI path, even though the API contract was already fixed.

### Manual reconstruction needed
- Manually waited for the queue open window, regenerated/used the clinic QR token, re-seeded a temporary dentistry doctor, and then confirmed the join page rendered two separate dentistry options.
- Manually removed the temporary doctor row after verification.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was a verification-only slice, but it repeated the same pattern: the stack found the queue pieces, yet the precise live window, token state, and temporary data seed had to be reconstructed by hand before the UI proof was meaningful.

## Task 39 - QueueJoin specialist label disambiguation

### User task
продолжай

### Gate result
- mode: gate_known_root_cause
- handoff required: yes
- handoff used: yes
- gate_misroute: yes
- override_used: yes
- known_root_cause_file: frontend/src/pages/QueueJoin.jsx

### What handoff solved well
- The gate identified the correct high-level area as a patient-facing join-flow label problem and produced a narrow override prompt.
- The override kept the first-touch file bounded to the join-page component instead of spreading into the queue API or unrelated admin screens.

### Missing relationship mapping
- The stack did not surface that the join-page label still collapsed distinct doctors into the same specialty-only text even though the API already returned doctor-shaped rows.
- It also did not surface that the visible proof relied on the same live QR/open-window conditions as the earlier join-flow verification.

### Manual reconstruction needed
- Manually introduced a label helper in `QueueJoin.jsx` that combines doctor name, specialty, and cabinet into a single distinct selector label.
- Manually verified the implementation with local lint and source-level inspection.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This is the same repeated pattern: the code change was narrow and correct once the file was known, but the relationship from API-shape to UI-label ambiguity had to be reconstructed manually. The gate also misrouted once before the approved narrow override was used.

## Task 40 - QueueJoin live proof with duplicated dentistry doctors

### User task
next step is to add or temporarily seed a second active doctor in one specialty and re-run /available-specialists

### Gate result
- mode: direct_execute
- handoff required: no
- handoff used: no
- gate_misroute: no
- override_used: no
- known_root_cause_file: none

### What handoff solved well
- none

### Missing relationship mapping
- The stack did not surface that the previous temporary doctor cleanup left no free doctor-role users available, so the live UI proof needed a brand-new temporary user.
- It also did not surface that the QueueJoin page needed a full reload after the temp doctor was created to reveal the second dentistry card.

### Manual reconstruction needed
- Manually created a temporary doctor-role user in the local database, linked it to a temporary dentistry doctor, and then reloaded the patient-facing join page.
- Manually confirmed the page rendered two distinct dentistry cards: one for `Dentist User` and one for `Temp Dentistry User`.
- Manually deleted both the temporary doctor and the temporary user afterward.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- The code path was already correct, but the live proof still required reconstructing the temporary seed data and browser refresh step by hand. That repeated the same multi-hop verification pattern seen in earlier queue and registrar tasks.

## Task 41 - QueueBatchRepository legacy user-id bridge removal

### User task
давай, но сначала коммит и пуш

### Gate result
- mode: gate_known_root_cause
- handoff required: yes
- handoff used: yes
- gate_misroute: yes
- override_used: yes
- known_root_cause_file: backend/app/repositories/queue_batch_repository.py

### What handoff solved well
- The gate narrowed the work to the batch queue repository and kept the change from spilling into the broader queue stack.
- The override prompt made the first-touch file explicit, which was enough to safely apply the smallest identity-resolution fix.

### Missing relationship mapping
- The stack did not surface that the repository still contained two legacy bridges after earlier queue canonicalization work: `Doctor.user_id` and `User.id -> linked_doctor`.
- It also did not distinguish the batch resolver from the already-fixed queue-open and queue-service paths, so the remaining bridge had to be found by manual search.

### Manual reconstruction needed
- Manually removed the fallback branches from `resolve_specialist_user_id()` so it now accepts only canonical `Doctor.id`.
- Manually verified the repository and its service counterpart compile cleanly after the change.

### Signals observed
- multi-hop gap: yes
- ownership ambiguity: yes
- manual graph reconstruction: yes

### Short verdict
- current stack sufficient: partial
- would LightRAG likely help here: yes
- This was another small but real identity-bridge cleanup: the file was found, but the relationship between batch queue resolution and the earlier queue canonicalization work still had to be reconstructed manually. The gate also misrouted before the narrow override was used.
