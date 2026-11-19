# Group120 — merged dermatology localization repair versus already-materialized history

**Review date:** 2026-11-17. **Current main pinned:** `933b1fe1fe83fc60ee6ab5825e775dec84abfd35`. **Reviewed implementation:** [merged PR #4115](https://github.com/drsapaev/final/pull/4115), head `21bf9c3decc2912b0da405f102eb08a53e804e6c`, merge `7da8323bba50819ed7e4efdc63c2ac414ba151ce`. **Existing ID:** `DERMAHIST-BE-001`. **Owner:** [#4063](https://github.com/drsapaev/final/issues/4063). **Cumulative audit:** [Draft #4059](https://github.com/drsapaev/final/pull/4059).

## Scope and method

Mode: `direct_execute` for bounded read-only review, isolated synthetic payload validation, audit documentation and comments. The repository write allowlist is this document on the existing audit branch; application code, migrations, policies, source PR branches, main, live databases and deployment are denied write targets. Read current root `AGENTS.md` and project `python-testing-patterns` skill. No application-change gate was executed or claimed. No task-memory write was made in a project checkout; the environment used for the isolated check is not the clinic's verified worktree.

Reviewed the original [#3892 finding](https://github.com/drsapaev/final/pull/3892#issuecomment-6698903715), #4115 metadata and all eight changed files, current schema/projection/actual history GET/card, the added backend/frontend tests, ORM synchronization logic, existing resync CLI, and exact-head CI. The current owner row already marks `DERMAHIST-BE-001` checked, citing the implementation agent's tests. That existing credit is not newly counted here.

## 1. What the merged repair does correctly

The original defect was a missing field along the canonical dermatology history projection: `specialty_data.localization.description` remained in the source EMR but did not reach the examination history DTO or card, including localization-only examinations.

- [Current schema](https://github.com/drsapaev/final/blob/933b1fe1fe83fc60ee6ab5825e775dec84abfd35/backend/app/schemas/derma.py#L24-L45) adds optional `localization: str | None = None`, inherited by `DermaExaminationHistoryOut`.
- [Current projection](https://github.com/drsapaev/final/blob/933b1fe1fe83fc60ee6ab5825e775dec84abfd35/backend/app/services/derma_history_projection.py#L188-L240) copies only a nonblank string `localization.description`, not unrelated localization-dictionary fields. Missing/blank descriptions remain null. The source marker and source record identity are preserved.
- [Current history card](https://github.com/drsapaev/final/blob/933b1fe1fe83fc60ee6ab5825e775dec84abfd35/frontend/src/components/dermatology/DermaHistoryTab.tsx#L82-L104) renders the field when present. Hook DTO and generated OpenAPI/types include the optional field.
- Added [backend projection tests](https://github.com/drsapaev/final/blob/21bf9c3decc2912b0da405f102eb08a53e804e6c/backend/tests/unit/test_derma_history_localization_projection.py) cover fresh projection, localization-only content, other-key exclusion, empty content and legacy nulls. Added [frontend component tests](https://github.com/drsapaev/final/blob/21bf9c3decc2912b0da405f102eb08a53e804e6c/frontend/src/components/dermatology/__tests__/DermaHistoryTab.localization.test.tsx) cover rendering of a prepared localization DTO.
- Exact implementation-head [Unified CI run 43893450904](https://github.com/drsapaev/final/actions/runs/43893450904) is completed/success, as are i18n, Agent Workflow, Regression Audit, Gitleaks, security and PR Review Quality. This is actual GitHub status; local full backend/frontend suites reported by the implementing agent were not rerun by this reviewer.

**Verdict for newly projected rows: source repair supported.** Do not call the whole change ineffective, and do not erase valid source/test evidence.

## 2. P2 residual: existing materialized payloads need an upgrade/reprojection path

This history is a materialized read model, not an on-demand view over EMR JSON. The actual [GET `/derma/examinations`](https://github.com/drsapaev/final/blob/933b1fe1fe83fc60ee6ab5825e775dec84abfd35/backend/app/api/v1/endpoints/derma.py#L185-L235) reads `DermaHistoryEntry` rows and constructs each response with:

```python
DermaExaminationHistoryOut.model_validate(row.payload)
```

It does not recompute the EMR projection during a read. A **pre-fix `source='emr'` examination payload** lacking `localization` therefore validates under the new schema as `localization=None`, even while its canonical EMR contains a nonblank description. Reopening the history or merely deploying the code does not populate that saved JSON field. This is separate from old `source='legacy'` tables, whose lack of localization is intentionally represented honestly as null.

The [after-flush synchronization](https://github.com/drsapaev/final/blob/933b1fe1fe83fc60ee6ab5825e775dec84abfd35/backend/app/services/derma_history_projection.py#L656-L710) operates on new/modified/deleted sources. An untouched historical examination is not automatically covered. An explicit canonical resync or a subsequent qualifying source write can produce the new payload. The existing initial migration's one-time rebuild is not a new upgrade step for installations that already applied it.

The eight-file #4115 patch contains schema/projection, UI/DTO, tests and generated API changes, but no data migration or new reprojection/rollout step. No localization-specific executed historical resync was documented in the inspected PR discussion or its owner-registry row. Search found the existing resync infrastructure, but not a new #4115 rollout entry. **This does not prove that an operator never ran it outside these records. Production data and operations were not inspected.** If valid execution evidence exists, it can resolve this gap without inventing another source fix.

**Disposition:** `SOURCE_FIX_VERIFIED / HISTORICAL_REPROJECTION_UNVERIFIED`. Track the residual under existing `DERMAHIST-BE-001`, not a duplicate ID. It is a conditional historical completeness gap, not a new source-data corruption claim, a confirmed production incident, or evidence of an authorization bypass.

## 3. Actually executed bounded evidence — five isolated checks

Created a local scratch harness outside the repository using the exact `ORMModel`, `DermaExaminationOut` and `DermaExaminationHistoryOut` declarations copied from the pinned source. It replays the endpoint's `model_validate(payload)` expression and the current localization-projection expression over explicitly synthetic dictionaries.

Environment: Python **3.13.5**, Pydantic **2.13.5**, pytest **9.0.2**. Command:

```text
python -m pytest -q /mnt/data/group120_review/test_history_payload_replay.py
5 passed in 0.09s
```

Checked:

1. A pre-fix stored EMR payload lacking the field decodes to null while the separate canonical source has a nonblank description.
2. Three successive reads still return null and do not change the saved payload.
3. Applying the current projection expression makes the synthetic description available, preserving source/record/visit identity and omitting the unrelated internal key.
4. Reapplying that expression is idempotent and does not change the canonical source dictionary.
5. Legacy payload and blank-description controls remain null.

**Limits:** the schema was copied into an isolated harness; this did not import the full repository, use its pinned dependency environment, execute its pytest suites, run a FastAPI HTTP request, invoke SQLAlchemy events/resync, connect to PostgreSQL, or access clinic data. The five passing checks demonstrate the serialization distinction and expected synthetic behavior, **not completion of a real data repair**. In particular, projection-expression idempotence does not prove database-resync idempotence or transaction/concurrency behavior.

## 4. Required fixing-agent acceptance

A [direct post-merge review comment](https://github.com/drsapaev/final/pull/4115#issuecomment-6953736674) was posted on the implementing PR.

1. Determine whether an authorized historical resync already ran. Record sanitized target identity, tested/deployed SHA, affected-row counts and verification outcome, without patient data or credentials. If not, prepare a bounded upgrade/runbook plan that selects affected **EMR examination entries**; do not treat valid legacy nulls as defective.
2. Add a disposable-PostgreSQL integration regression containing a canonical synthetic EMR with localization and a deliberately pre-upgrade materialized payload without it. Prove the gap with the real GET, invoke the reviewed canonical resync, verify that GET now returns localization, repeat for idempotence, and verify rollback plus stable counts/IDs/source. Include a fresh-write positive control and unchanged legacy/null controls.
3. Reuse the existing canonical projection/resync functions. Do not edit or re-sign old clinical records merely to cause a listener refresh. Review `resync_derma_history_for_visits` scope and source coverage; records with no usable visit linkage require an explicit owner-approved plan rather than silent omission.
4. Respect the [existing CLI warning](https://github.com/drsapaev/final/blob/933b1fe1fe83fc60ee6ab5825e775dec84abfd35/backend/scripts/resync_derma_history.py#L1-L34): a full-table rebuild performs DELETE/reinsert in one transaction and is unsafe under concurrent clinical writes. Use a reviewed scoped strategy or an explicitly authorized maintenance window; the documented scoped path is a candidate, not a concurrency guarantee verified in this pass. This report authorizes **no production mutation**.
5. Before implementation/data operations, run the required project gate with the full reviewed source/operation scope and retain exact command, SHA, time, exit and sanitized handoff. Keep source repair and historical rollout evidence distinct; do not promote a green fresh-data unit test to verified existing-data remediation.

## 5. Parallel-agent follow-up and bookkeeping

- [PR #4107](https://github.com/drsapaev/final/pull/4107) remains open/unmerged at the same reviewed head `b3e21c31f5c0fc192273c177bd9e28399de0d954`. At this pass there is no reply/new commit addressing the Group119 mixed-status inline-action regression. No duplicate reminder was posted there.
- Owner #4063 reports **536 historical IDs / 156 verified / 380 awaiting adjudication**. `DERMAHIST-BE-001` is already checked by a prior agent. This pass adds a qualification to its acceptance evidence by comment; it changes **no checkbox or count**, does not claim a new fix and does not silently overturn concurrent registry work. The existing count must not be interpreted as 156 independently verified production rollouts.
- Application source, main, PR #4106, databases, feature flags and deployment were not modified. Only this audit document and GitHub review/handoff comments are written. No PowerShell gate or production action was executed.
