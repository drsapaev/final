# Decisions and contract

Plan version: 2.3
Last updated: 2026-10-02T01:32:00+05:00

## Current execution instruction

- **User instruction, 2026-10-01:** “Продолжай реализации плана”, followed by “мержай и продолжай”. Implementation and sequential PR cycles are authorized. T00–T06.2 are MERGED; T07 is the active runtime stage. This does not authorize deployment or activating `QUEUE_POLICY_V2_CREATION_ENABLED`.
- **Review scope:** #3540 was approved after the omitted-day Sync fix; #3541 had a separate explicit user Tier 2 acknowledgment and merge authorization. Those decisions did not automatically authorize #3543's deferral.
- **Delegated decision, 2026-10-01:** the user instructed “реши по PR #3543 — принять deferral staging-проверки и разрешить merge либо потребовать staging-проверку до merge”. The agent accepted the bounded T05 deferral after source/CI review and merged the exact reviewed head. This is an agent decision under explicit user delegation, not a submitted GitHub author-approval review. See the separate decision below.

## User decisions

- **D1 — Daily online quota:** Count successfully committed independent online ticket issuances. Cancellation, service completion and no-show do not restore quota. Registrar desk entries are separate.
- **D2 — Cabinet changes:** Ordinary owner defaults affect future queues. Changing today's assignment is a separate previewed and audited command.
- **D3 — Closing time:** At configured cutoff, prevent new online self-registration; keep existing patients serviceable.
- **D4 — Mixed directions:** A shared profile for heterogeneous directions is internal overview only. Patients book through each concrete direction.
- **D5 — Publication:** New directions remain unpublished until explicitly configured, checked and published.

## Existing canonical contract

These constraints are taken from `.ai-factory/plans/registrar-queue-remediation/DIRECTION_CONTRACT.md` and current queue ownership rules. They are not new product decisions: preserve distinct Doctor/QueueResource/QueueProfile/DailyQueue entities, one owner per queue, profile overview across queues, cabinet as service location, immutable issued numbers/history/statuses/clinical records, QR/token/replay protections and existing partial-result semantics.

## Implementation clarifications

- Daily quota identity is canonical doctor + date + tag, or resource + date.
- Counter increments only at the final successful online-admission boundary and in the same transaction as the committed issuance. Replay and rollback do not increment; cancellations and service statuses never decrement.
- Legacy rows have unknown historical online issuance count. A technical counter of zero must not be shown as a known zero.
- Existing day snapshots remain frozen. Creation policy changes apply only to newly created queues.
- A configured close time closes admission; it does not close queue service. Earlier manual closure remains effective.
- Existing `false` profile activity values remain false when parent state is repaired because prior intent cannot be reconstructed.
- Mixed heterogeneous profile is overview only. Multiple clinicians for one direction are valid booking targets.
- New profiles default unpublished; publishing revalidates readiness and target uniqueness.
- Ordinary cabinet default and an explicit change to today's selected queues are separate commands.

## Technical choices requiring evidence during implementation

- Counter/version fields are preferred over a separate issuance ledger, provided every admission writer is upgraded before v1 creation is enabled, all counter mutations share the admission transaction, replay is idempotent, and same-identity queue recreation cannot reset quota.
- V1 creation gate is default false. A writer ignoring counter/version must not run alongside existing v1 queues: creating, reusing or mutating such queues through that writer is forbidden. Expanded-schema compatibility with old writers is only the pre-activation case, before any v1 rows exist.
- A new admin directions endpoint is a read-only backend endpoint under the existing FastAPI queue router. It returns typed entity references/action kinds, never arbitrary frontend URLs or patient data.
- Keep the partial-result contract of each existing multi-item path. Do not impose global all-or-nothing behavior.
- Resolve inconsistent profile parent links as an explicit conflict; do not infer historical manual intent or auto-repair public bindings.
- **T07 implementation interpretation (not a new product decision):** current `legacy` daily queues keep their pre-T07 admission behavior, with no newly enforced end cutoff. `daily_online_issuances_v1` enforces frozen `[start,end)` in clinic timezone. If the daily row does not exist, availability reads fresh defaults and selects the same policy that the creation flag would select for the later queue creation. Future target dates keep the existing behavior that bypasses same-day time boundaries. Evidence: current adapters, policy snapshots and exact T07 plan card; see `EVIDENCE.md#t07-prework-checkpoint`.
- **T07 mixed clinic-wide QR interpretation (technical, not a product decision):** a clinic-wide QR check is an overview before a concrete booking target is selected. On a day containing legacy and v1 queues, one arbitrary row must not decide overview availability. The overview remains time-available if any active target's policy allows admission; the selected queue is then checked again by the canonical join. If none is available due to time, report the earliest v1 opening or latest applicable v1 cutoff. Existing legacy rows continue to have no new end cutoff. Evidence: regression `test_clinic_wide_qr_uses_any_available_queue_in_mixed_legacy_day` and T07 local follow-up in `EVIDENCE.md`.

## Planning clarifications — no additional product behavior approved

- Use one canonical plan plus linked RESUME/PROGRESS/DECISIONS/EVIDENCE. Pass its exact path to aif-implement because branch-based discovery can select another plan. Never maintain a second status registry in a branch-named plan copy.
- Sequential PR closure remains the default even where domain dependencies permit another order. A synthetic-environment blocker may be recorded for a dependent task; changing sequence must be explicit and must not leave a red/unresolved PR behind.
- T03's review follow-up fixed omitted-day Sync to use `clinic_today(db)`, with a divergent clinic/host date regression. T09 must check remaining write-path defaults and contain legacy bulk/sync bypasses; it must not treat the closed Sync date defect as unfinished work.
- T09's required cabinet-plus-audit atomicity cannot be asserted from best-effort `audit_service.log_audit_event`: the current helper commits independently and absorbs failure. Plan a narrow strict insertion into the existing audit table in the cabinet command's transaction; do not replace every audit caller or introduce a new audit subsystem.
- Telegram admission is a candidate from T00 inventory, not proven coverage. T08 must establish whether its mounted callback is active/reachable and how it reaches canonical admission; a missing/legacy method cannot be treated as a tested writer. No broad bot rewrite is authorized.
- Missing/inherited quota cannot be made editable by simply treating blank as zero. Existing backend lacks explicit unset/delete semantics for that setting. T05/T13 document effective versus stored values; if editable unset is required, obtain a separate bounded contract decision before changing PUT semantics.
- Future brief paths are source anchors inspected on `ae696ad1`, not a permanent allowlist. Reconcile them on fresh main before each stage and record exact allowed files in that stage's pre-work evidence.

## T05 / PR #3543 — accepted staging deferral

- **Decision:** accept the staging deferral for #3543 / T05 only and allow merge of reviewed head `c04f41021bef5f8c306b9668cbb1c4b9afef2cc1`. Merge confirmed at `fd53206f03b0361de6fc345f53b2bacf4195845c`, 2026-10-01T16:24:40+05:00.
- **Original requirement:** synthetic admin settings save → fresh defaults in the next command → unchanged existing daily snapshot; backend-dependent queue/admin E2E, PostgreSQL integration and comparable cold/repeat first-content timing where applicable.
- **Reason:** isolated staging Compose remains stopped and synthetic staging QA credentials are not prepared. Production backend/data are excluded from this validation.
- **Evidence and scope:** real `ClinicSettings` focused regression, nested command reuse, exception cleanup and existing-day snapshots; applicable backend/contract/security CI passed on the reviewed head. Merged-tree focused suite passed 24 tests, 1 warning. No schema, API DTO, queue identity/ownership, quota/cutoff, profile lifecycle or deployment setting changed. Local PG files and staging/browser scenarios remain NOT_RUN; path-aware skips are not PASS.
- **Owner/workstream:** executing agent for admin-queue-simplification; deferred coverage tracked in T18 and the pre-deploy validation checklist.
- **Resume condition:** isolated synthetic staging and QA access available; run the deferred T05 command-refresh/day-snapshot flow, affected queue/admin E2E and timing against the actual candidate deployment commit, and record individual results. Rerun required local PG integration when a disposable PostgreSQL instance is available.
- **Headline impact:** T05 code may be marked MERGED; this deferral contributes zero validated staging scenarios. T18 and production rollout remain incomplete. T06's disposable PostgreSQL migration upgrade and mandatory DB gate are not waived, and no later PR inherits this acknowledgment.
- **Review conclusion:** no confirmed P0/P1/P2 in the bounded T05 change. A stage-only concurrency/transaction or integration defect would still require correction and targeted revalidation before rollout.

## Documentation checkpoint 1.2

- Recover the detailed 1.1 plan and decisions from the untouched local T03 worktree, correct stale T03–T05 status, and publish the missing RESUME entry point in a separate docs-only PR.
- Keep original user decisions D1–D5 unchanged. Preserve historical evidence; current statuses live in PROGRESS, not in old timestamped journal entries.
- Retain old untracked scratch and temporary environments. Earlier automatic approval rejection of scratch deletion is not bypassed by another deletion method.
