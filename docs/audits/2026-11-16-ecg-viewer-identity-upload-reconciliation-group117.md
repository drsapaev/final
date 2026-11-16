# Group117 — ECG viewer multipart, patient isolation, and extension-driven XML parse reconciliation

**Review date:** 2026-11-16. **Pinned current main:** [`835eb01b6a664ef3485a6ce4e1590313ca937b75`](https://github.com/drsapaev/final/commit/835eb01b6a664ef3485a6ce4e1590313ca937b75). **Owner:** [#4063](https://github.com/drsapaev/final/issues/4063). **Cumulative audit:** [Draft PR #4059](https://github.com/drsapaev/final/pull/4059). Three historical owner IDs were still [ ] when independently checked: `ECGVIEW-FE-001`, `ECGVIEW-FE-002`, `ECGVIEW-FE-003`. Original claims are from the [#3886 audit (2026-11-06): ECG upload/viewer and XML parsing](https://github.com/drsapaev/final/blob/186e598006bb3245dc5b7742aedfb9b597000e1d/docs/audits/2026-11-05-qr-join-public-flow-source-review.md#L575-L605) and [extension dispatch observation](https://github.com/drsapaev/final/blob/186e598006bb3245dc5b7742aedfb9b597000e1d/docs/audits/2026-11-05-qr-join-public-flow-source-review.md#L645-L651).

**Merged remediation provenance:** [PR #3941](https://github.com/drsapaev/final/pull/3941), head `602eda5284f1b980b279130f4e11c1325373e8dc`, merged. Its exact-head [Unified CI](https://github.com/drsapaev/final/actions/runs/42744569964) is **NOT** the #3941 run (that reference belongs to #3965); **verify #3941's own actual Unified run before crediting**. This report's evidence additionally includes [PR #3965](https://github.com/drsapaev/final/pull/3965), head `3698e283f1f26915aefa71c751849ccb42a5f472`, [CI 42744569964](https://github.com/drsapaev/final/actions/runs/42744569964) **SUCCESS**, which includes current updated ECGViewer contract controls. No local tests were executed by Group117 reviewer; all tests below are checked-in behavioral definitions and prior exact-head GitHub results.

## ECGVIEW-FE-001 — FIXED_VERIFIED_ON_MAIN

**Historical P1:** `formData.append('file', String(file))` sent the literal `[object File]` string, not binary multipart `File` expected by backend `UploadFile`.

- Current [`ECGViewer.tsx`](https://github.com/drsapaev/final/blob/835eb01b6a664ef3485a6ce4e1590313ca937b75/frontend/src/components/cardiology/ECGViewer.tsx#L357-L402) appends the binary via `formData.append('file', file, file.name)`, sending patient/visit IDs separately.
- [`ECGViewer.upload.test.tsx`](https://github.com/drsapaev/final/blob/835eb01b6a664ef3485a6ce4e1590313ca937b75/frontend/src/components/cardiology/__tests__/ECGViewer.upload.test.tsx#L124-L151) mounts the component, drops a synthetic XML `File`, captures `/files/upload` request, asserts the multipart `file` is a `File` with matching name, size and bytes, and patient/visit IDs.
- **Classification:** FIXED_VERIFIED_ON_MAIN by source+behavioral test+actual completed CI; no claim of a new real backend TestClient upload by auditor.

## ECGVIEW-FE-002 — FIXED_VERIFIED_ON_MAIN (original scoped frontend isolation)

**Historical P1/P2:** same mounted ECG viewer could keep A's files, preview/parsed parameters and late async callback results after switching to patient B.

- Current [`ECGViewer.tsx`](https://github.com/drsapaev/final/blob/835eb01b6a664ef3485a6ce4e1590313ca937b75/frontend/src/components/cardiology/ECGViewer.tsx#L284-L354) derives `ownerKey` from patient and visit, increments a synchronous epoch on changes, resets local file list/selection/preview/AI/ECG state in its effect, and checks captured epoch before async upload or parsing/UI commits. Parent `EcgTab` also keys by patient/visit, providing extra isolation.
- [`ECGViewer.upload.test.tsx`](https://github.com/drsapaev/final/blob/835eb01b6a664ef3485a6ce4e1590313ca937b75/frontend/src/components/cardiology/__tests__/ECGViewer.upload.test.tsx#L196-L255) rerenders the same mounted viewer from synthetic A to B, asserts A's file disappears, then holds A's upload response, switches to B and resolves A: stale file remains absent. This is a real component behavior test, **not** a full browser proof of every preview/delete/download interaction. The specific original local-state and late-upload issue has a defensible fix; no authorization claim.
- **Classification:** FIXED_VERIFIED_ON_MAIN for the original reported local UI identity leak. Re-open a new distinct finding if preview/delete race can be shown independently; do not infer it from absence of a special test.

## ECGVIEW-FE-003 — FIXED_VERIFIED_ON_MAIN (MIME mismatch only)

**Historical P2:** a valid `.xml` file with browser MIME `application/xml` or empty MIME skipped parser while `text/xml` succeeded.

- Current [`ECGViewer.tsx`](https://github.com/drsapaev/final/blob/835eb01b6a664ef3485a6ce4e1590313ca937b75/frontend/src/components/cardiology/ECGViewer.tsx#L327-L407) accepts `application/xml`, identifies parse-eligible `.xml` / `.scp` by filename and always calls `parseECGFileData` for eligible extension, not only MIME `text/xml`.
- [`ECGViewer.upload.test.tsx`](https://github.com/drsapaev/final/blob/835eb01b6a664ef3485a6ce4e1590313ca937b75/frontend/src/components/cardiology/__tests__/ECGViewer.upload.test.tsx#L153-L195) parameterizes synthetic `application/xml`, empty MIME, `text/xml`, asserts post-upload parsed device record `POST /cardio/ecg`, and negative PDF does not parse. [`ECGParser.contract.test.tsx` extension control](https://github.com/drsapaev/final/blob/835eb01b6a664ef3485a6ce4e1590313ca937b75/frontend/src/components/cardiology/__tests__/ECGParser.contract.test.tsx#L419-L434) independently pins the empty-MIME flow.
- **Classification:** FIXED_VERIFIED_ON_MAIN for the *dispatch by extension* problem only. **Do not conflate** with separate `ECGPARSER-FE-001` schema/identity/unit validation, which remains open and can admit unrelated XML carrying e.g. `<heartRate value="75"/>`. More permissive dispatch is only safe if content is strictly validated by a follow-on parser; no such full validation was claimed.

## #4106 acceptance, still blocked despite CI success

[Draft PR #4106](https://github.com/drsapaev/final/pull/4106), current head `17fba86e2c9fe3ed5505bae133478327b39c2dbb`, [Unified run 43886315404](https://github.com/drsapaev/final/actions/runs/43886315404) **COMPLETED SUCCESS** for frontend unit/E2E/build/lint and required gate, with i18n, security, Agent Workflow, Regression Audit, Gitleaks and PR Review Quality all successful. The PR is exactly two scoped cardiology files, no commits behind current main, still open Draft. **Formal GitHub code reviews: zero** as of last query; **actual required `ai/langgraph/scripts/run_agent_gate.ps1`: NOT RUN** in verified checkout. The GitHub `PR Required Gate` passing is NOT execution of `run_agent_gate.ps1`. Keep `DOCFLOW-FE-004` unchecked, do not merge or deploy.

## Owner accounting

At start: **536 unique IDs / 149 credited / 387 pending**. Proposed three new [x] entries above (provided owner stays unchanged): **152 credited / 384 pending**. **`ECGPARSER-FE-001` remains open** and is a separate source-confirmed schema/units concern, not a production-incident claim. This is docs-only reconciliation on Draft #4059, with no ECG source writes, no gate, no new implementation PR and no main merge.
