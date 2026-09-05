# Design: Desk Registration → Real Queue Entries (QD)

**Status:** DRAFT for operator approval (no implementation in this PR)
**Decision:** Option **A** — desk registration joins the real queue machinery. One `QueueEntry` per logical queue route (`queue_tag`), not per visit, not per service.
**Author evidence base:** live prod audit 2026-09-05 (patient 36: visits 25/26, `queue_entries` 0, `daily_queues` 0) + code walk below. Incident record: `docs/incidents/2026-09-02-supabase-rls-disabled-in-public.md` (same checkout, sibling session).

---

## The five proofs requested by the operator

### 1. Which existing batch/join API is canonical

**For the desk wizard (visit creation):** the flow ALREADY routes through the queue machinery — no new API needed:

```
POST registrar-wizard cart (_cart.py:188)
  → RegistrarWizardQueueAssignmentService.assign_same_day_queue_numbers()
    → MorningAssignmentService._get_visit_queue_tags(visit)     # tags from VisitService→Service.queue_tag
    → for each tag: prepare_wizard_queue_assignment(...)         # morning_assignment.py:478
      → queue_service.get_or_create_daily_queue(...)             # SSOT numbering
```

**For "add services to an existing patient" (edit path):** canonical is `POST /api/v1/registrar-integration/queue/entries/batch` (`registrar_integration/_today_queues.py:832`) — groups by `specialist_id`, duplicate-detects, delegates to the same `queue_service` SSOT.

**For self-service:** QR join (`_qr_queue_join` flows) converges on the same SSOT.

All three paths terminate in `queue_service.get_or_create_daily_queue` + numbered `queue_entries` — the single place numbering lives. QD reuses these; **no new API**.

### 2. Exact grouping key for desk services

**`Service.queue_tag` collected from the visit's `VisitService` rows** — implemented today in `MorningAssignmentService._get_visit_queue_tags` (morning_assignment.py:352). One entry per distinct tag. Example (the reported patient):

```
L14 + L16 + L15 (all queue_tag='general') → 1 entry, queue 'general'
S01  (queue_tag='stomatology')            → 1 entry, queue 'stomatology'
```

**⚠️ Catalog data discrepancy the operator must rule on:** the reported service codes were "L02, L12, L17, S01", but `L02` does not exist in `services`; the actual visit services are L14/L15/L16, and **all lab services are currently tagged `queue_tag='general'`** (not `'lab'`). Routing works, but lab patients will land in the **general** queue. If the operator wants a separate `lab` queue, that is a **catalog re-tag pass** (UPDATE services.queue_tag), decidable independently of QD-1.

### 3. requires_doctor=true / false handling

`Service.requires_doctor` **exists** (prod: 22 true / 44 false) and the tag data is complete (0 NULL queue_tags of 66 services). But `prepare_wizard_queue_assignment` **does not consult it**: for ANY doctorless visit it falls back to the resource-doctor mapping (`lab→lab_resource`, `general→general_resource`, `stomatology→stomatology_resource`, `ecg→ecg_resource`; morning_assignment.py:501-515).

- QD-1 keeps this mapping (the operator's "resource-doctor compatibility" stage).
- QD-2 will consult `requires_doctor`: true → assignment REQUIRES an explicitly chosen doctor (wizard enforces doctor selection for such services; QR enforces the doctor-pick step) and the resource fallback is rejected with a configuration error; false → tag-owned queue (doctorless) is legitimate.

### 4. Can visit+queue be atomic without new architecture

**Yes — the transaction seam already exists, with one gap.** `_cart.py` creates visits → invoice → `assign_same_day_queue_numbers` → `db.commit()`, and P2-1c (already merged) rolls back and clears assignments on any per-tag failure (partial assignment unsupported, documented contract).

**The gap:** when the loop yields zero assignments, `_cart.py` still commits the visits (silent no-queue state — exactly patient 36). QD-1 closes it: **if a visit's services produced queue_tags and `queue_assignments` is empty after the loop → abort the cart** with an explicit configuration error (409/422, per the operator's guard) naming the offending service. With QD-0 provisioning (below) this becomes a configuration-guard that should never fire in normal operation.

### 5. Where the UI renders queue from Visit instead of QueueEntry

- **Wizard success / patient card** (the reported "Очередь: Специалист #None, Специалист #None"): renders `Специалист #{specialist_id}` from the VISIT (doctorless → None). After QD-1 the cart API response already carries real `queue_numbers`; the card must render **those** (target shape: `Лаборатория № 7 / Стоматология № 3`). Exact component sits in the onboarding/UX track of the parallel session — coordinate before editing.
- **Talon print** (`panelPrint.ts`): since #3058 falls back to `В-<visit_id>` — per the operator this stays ONLY as a defensive fallback; with QD-1 the normal path prints the real queue numbers returned by the cart.
- `QueueCabinetManagement` (admin) already renders from `daily_queues` — correct source, no change.

---

## Root cause of the reported incident (QD-0, provisioning)

`prepare_wizard_queue_assignment` needs, for a doctorless tag, a **resource doctor**: User (`lab_resource`/`general_resource`/`stomatology_resource`/`ecg_resource`, active) + linked `Doctor` row. **None of the four users exist on production** → `return None` for every tag → zero assignments → the reported failure. The legacy diagnostic `scripts/legacy_scripts/backend/diagnose_assignment.py` even checks `lab_resource` existence — this gap is a known historical pitfall that was never provisioned on the new prod database.

**QD-0 (implementation PR after design approval):** idempotent data migration `0055_queue_resource_doctors` creating the four users (role per calling-permission needs, `is_active=true`) + linked Doctor rows (specialty == the queue_tag they serve, so same-specialty call permissions work per ADR-001), skipping any that exist. This is data provisioning, mirroring how 0049 proved data migrations are acceptable. After QD-0, desk registration produces real numbered entries with zero code changes (the existing path starts working) — verifiable live within minutes.

## Staging

| Stage | Content | Risk |
|---|---|---|
| QD-0 | Provision 4 resource users+doctors (idempotent data migration) | minimal — dormant accounts |
| QD-1 | Cart aborts on missing routing + UI renders cart-returned queue numbers (+ talon fallback demoted to defensive) | small — guarded by new tests |
| QD-2 | Doctorless queue ownership: `requires_doctor` consulted; DailyQueue.specialist_id nullable / explicit queue-resource model | medium — queue schema touch, separate design per operator's brief |

## Explicit non-goals / boundaries

- Medical Specialty Catalog (#3010) is the SSOT for **doctor specialty**; it is NOT the SSOT of patient routing (`QueueProfile`/`queue_tag` stays). No coupling beyond QD-2's needs.
- Queue fairness, numbering (`queue_time`), and the P2-1c atomicity contract are untouched.
- `В-<visit_id>` print fallback remains as a defensive last resort only.
