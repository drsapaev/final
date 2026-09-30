# Decisions and contract

Plan version: 1.0
Last updated: 2026-09-30

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
- V1 creation gate is default false. Old writers must not create v1 rows while ignoring quota fields.
- A new admin directions endpoint is a read-only backend endpoint under the existing FastAPI queue router. It returns typed entity references/action kinds, never arbitrary frontend URLs or patient data.
- Keep the partial-result contract of each existing multi-item path. Do not impose global all-or-nothing behavior.
- Resolve inconsistent profile parent links as an explicit conflict; do not infer historical manual intent or auto-repair public bindings.
