# Retrospective Code Review — audit/fix PR #3803–#3919 (2026-11-07)

> **Type:** independent retrospective audit register (docs-only); **not** a runtime fix, security approval, financial/clinical certification, or permission to merge/deploy.
> **Scope:** `drsapaev/final`, PR numbers #3803–#3919, GitHub state checked 2026-11-07 (Asia/Tashkent).
> **Mode:** `direct_execute`, narrow documentation-only write. Root `AGENTS.md` read; repository source/tests/audit ledgers consulted. Only this new Markdown file is authorized. No production data, EMR/payment/queue mutations, secrets, migrations, source edits, deployments, merges or changes to existing PRs. A follow-up fix in protected domains must run the mandatory repo gate before modifications.

## Executive verdict

- GitHub PR search yielded **92 extant PRs** in this numeric range, including **19 docs**, **57 `fix`**, **5 `test`**, **1 `ci`**, and **10 other** (including open Palette PRs). Missing numeric IDs are not classified as PRs.
- Of **57 `fix` PRs**, **54 are merged**, and **3 are closed without merge**: [#3885](https://github.com/drsapaev/final/pull/3885), [#3896](https://github.com/drsapaev/final/pull/3896), [#3919](https://github.com/drsapaev/final/pull/3919). The latter are superseded/duplicate paths; **do not count their patches as deployed**. #3919 was superseded by merged #3918; #3896 was an alternative to merged dental fix wave #3903.
- For the 54 merged `fix` PRs, **21 have a substantive GitHub Review body found in the review history** and **33 do not have such an independently inspectable final review body**. This is a **review-evidence gap**, not evidence that 33 PRs have defects. Automated checks, PR description assertions, review receipt stubs and inline replies are not equivalent to a substantive post-fix review at final HEAD. Some 21 were reviewed pre-merge or at an earlier commit; they are **not all certified at final HEAD**.
- **Two new source-backed follow-up candidates** were confirmed in current `main` code during this pass: RETRO-FIN-001 (P1 candidate, client-request replay without payload binding; #3864) and RETRO-LAB-001 (P2 candidate, mixed-intent leave guard; #3918). **No synthetic regression executed**, so priorities remain provisional and production impact is not asserted.
- The historic docs ledgers represent snapshots at their recorded dates, not an automatically updated final truth; a 'RESOLVED' audit label or a green CI alone does not establish a post-fix independent review.

## Method and evidence strength

1. Enumerated accessible PR numbers, read `get_pr_info` for merged status of every relevant `fix` and the latest PRs, read `list_pull_request_reviews` for all 57 `fix` PRs, and inventoried changed files/patch sizes/test files for the **33 merged `fix` PRs without a substantive review body**. Inspected source diffs and relevant tests more deeply for #3864, #3917, #3918; checked the two candidate code paths again from the current default branch. Previous PR #3902–#3916 post-merge review results and their subsequent fix PRs were cross-checked for duplicate reporting.
2. 'Substantive Review body' is a **conservative discoverability heuristic**: a human-readable review body explaining code/evidence, not merely an empty `COMMENTED` event or automated receipt. It does **not** verify reviewer independence, correctness, tested SHA, or absence of other inline comments. Do not interpret 'no body' as 'nobody looked at the code'.
3. Read source-audit documents #3803, #3813, #3833, #3875, #3882, #3886 and #3892, including their dated status notes. Did **not** run local Vitest, pytest, PostgreSQL races, browser E2E, staging, Telegram sends, or live payment/clinical actions; did **not** fetch production logs or interact with actual patients.
4. This dossier is an **initial independent review pass and complete evidence-inventory**, not 54 full line-by-line sign-offs. Each unverified high-risk PR remains in the review queue below.

## Finding RETRO-FIN-001 — P1 candidate: payment idempotency replay is not bound to the original payment intent

- **Introduced:** [#3864](https://github.com/drsapaev/final/pull/3864) (merged; no substantive submitted review body found). **Current source:** [`backend/app/api/v1/endpoints/cashier/_payments.py` lines 52–96, 522–531, 804–817](https://github.com/drsapaev/final/blob/main/backend/app/api/v1/endpoints/cashier/_payments.py); [`CashPaymentModal.tsx` lines 85–102, 147–155](https://github.com/drsapaev/final/blob/main/frontend/src/components/payment/CashPaymentModal.tsx).
- **Observed:** `_replay_payment_client_request` searches only by `client_request_id` and compares `endpoint`. Both create routes check for replay **before** validating the requested patient, visit(s), amount or method. The stored anchor has `endpoint`, `response_payload`, `created_by`, but no normalized request fingerprint or patient/visit binding. The modal keeps one UUID in `useRef` for its entire mounted lifetime and updates the amount if its appointment prop changes.
- **Repro to add (synthetic; not yet executed):** successfully POST a partial payment for visit A with key K. POST again to the **same endpoint** using key K but a **different visit B / patient / amount**. Current replay branch returns A's successful stored response (HTTP 200) and creates no payment for B, without a mismatch error. A legitimate retry with an IDENTICAL request should still return the original response, including after the visit has since been settled.
- **Conditional effect:** reusing K for a genuinely new intent (for example a same-mounted modal whose appointment changed, or an integration bug/compromised client) yields an apparent payment success unrelated to the newly submitted intent. A role-authorized caller with a known prior K can also receive the old payment metadata without a request-owner check on this replay path. This is **not proof** that a random external user can guess UUIDs or that a real payment was misattributed.
- **Required fix:** persist and compare a canonical intent fingerprint (endpoint + patient/visit allocation + amount + method and other semantic fields) and relevant authorization scope before replay; reject a mismatched K with HTTP 409 without charging. Retain atomic payment+anchor commit and winner-replay for byte-equivalent duplicates; reset/generate an explicit new key for a deliberate new payment intent. Add same-key/different-payload + same-key/cross-patient + same-key/identical-response + concurrent-race regressions in disposable PostgreSQL.

## Finding RETRO-LAB-001 — P2 candidate: pending leave policy can be replaced by a context transition

- **Introduced:** [#3918](https://github.com/drsapaev/final/pull/3918) (merged; no substantive GitHub Review body found). **Current source:** [`useDirtyTransitionGuard.tsx` lines 183–219](https://github.com/drsapaev/final/blob/main/frontend/src/components/laboratory/hooks/useDirtyTransitionGuard.tsx), [`LabDirtyGuardContext.tsx` lines 513–544](https://github.com/drsapaev/final/blob/main/frontend/src/components/laboratory/LabDirtyGuardContext.tsx).
- **Observed:** when `pendingTransitionRef.current !== null`, the new guard rejects an incoming transition **only if the incoming** `transitionOptions.intentPolicy === 'leave'`. A pending logout/route-leave dialog can therefore be overwritten by a second transition using default `context` policy; `pendingTransitionRef.current` is assigned anew. In addition, the `!hasDirty` fast path precedes the pending-ownership check and can replace/execute an operation while a dialog remains pending.
- **Repro to add (synthetic; not yet executed):** register dirty report, invoke `guardRouteLeave(logout)` so Save/Discard/Cancel opens, then programmatically issue a context-scoped in-lab URL/report intent while that dialog is pending. Confirm Save/Discard. The stored pending action changes from the originally requested logout to the newer context action. Existing `LabDirtyGuard.intentIntegrity.test.tsx` covers `leave → leave`, **not** `leave → context` or dirty-state flip while leave pending.
- **Required fix:** persist the policy on the **pending** transition and reject attempts to supersede an existing pending **leave**, regardless of the incoming policy, before checking `hasDirty`; preserve intended context→context supersession. Add explicit `leave→context`, `leave→leave`, `context→context`, `leave + dirty→clean` regressions and browser-sentinel E2E with only synthetic records.

## Audit origins and status freshness

| Origin PR | Ledger | Snapshot caveat / recommended reconciliation |
| --- | --- | --- |
| [#3803](https://github.com/drsapaev/final/pull/3803) | Registrar frontend | Current ledger header says **38/69 RESOLVED, 31 REPRO-PENDING** as of 2026-11-04. Subsequent #3876–#3878 may change practical coverage: **do not publish 31 as the current unfixed count** without ID-by-ID reconciliation. |
| [#3813](https://github.com/drsapaev/final/pull/3813) | Cashier frontend | Header says **15/38 resolved, 23 REPRO-PENDING** as of 2026-11-04; later cross-domain fix batches need reconciliation. Payment server idempotency #3864 needs the independent replay-contract test above. |
| [#3833](https://github.com/drsapaev/final/pull/3833) | Cross-module follow-up | Registrar/cashier/QR follow-up and refund DTO findings; dedupe against #3876–#3878 rather than counting the same observation twice. |
| [#3875](https://github.com/drsapaev/final/pull/3875) | QR realtime and display board | P1 board defects #3884 targeted; remaining P2 and owner/WS behavior require final-HEAD source checks and websocket synthetic tests. |
| [#3882](https://github.com/drsapaev/final/pull/3882) | Backup/restore BR-001–022 | Ledger records 19 items as fixed in merged #3883/#3887/#3889/#3890 and 3 items closed through host/operator evidence. **Host closure is not code-fixed**, and actual restore-of-attachments/prod DR has not been certified by this retrospective. |
| [#3886](https://github.com/drsapaev/final/pull/3886) | Queue, laboratory, cardiology and EMR source audit | Broad ledger of **120 source findings**. PR #3918 describes **33 addressed in rounds 1–12** and 6 more in round 13; verify distinct finding IDs and tests in the latest main before declaring remainder or release readiness. |
| [#3892](https://github.com/drsapaev/final/pull/3892) | Dental/dermatology 27 findings | Claimed implementation waves #3903/#3906/#3908; earlier five+five inline findings received subsequent fixes/replies. Some review threads remained unresolved after merge; do not count a thread's unresolved flag as proof of uncorrected code. |

## Fix PRs with no substantive formal Review body — 33 merged / prioritized re-review

Every row below refers to a **merged** PR; 'test files' counts files whose changed path matches test naming, **not executed/passing tests**. Source diffs for these 33 PRs were inventoried. This table is a **work queue**, not 33 completed independent code reviews.

| Fix PR | Domain / reason to re-review | Test files in diff | Evidence status |
| --- | --- | ---: | --- |
| [#3814](https://github.com/drsapaev/final/pull/3814) | Cashier: долг с возвратами | 1 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3825](https://github.com/drsapaev/final/pull/3825) | Registrar: ID пациента | 1 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3826](https://github.com/drsapaev/final/pull/3826) | Registrar: перенос визита | 2 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3827](https://github.com/drsapaev/final/pull/3827) | Registrar: номер талона, backend | 3 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3838](https://github.com/drsapaev/final/pull/3838) | Cashier: сумма наличной оплаты | 2 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3839](https://github.com/drsapaev/final/pull/3839) | Cashier: API возвратов | 2 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3840](https://github.com/drsapaev/final/pull/3840) | Cashier: polling оплаты | 2 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3843](https://github.com/drsapaev/final/pull/3843) | Registrar: подтверждение команд | 4 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3844](https://github.com/drsapaev/final/pull/3844) | Registrar: PHI в диагностике | 2 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3845](https://github.com/drsapaev/final/pull/3845) | Registrar: контракт очереди | 2 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3846](https://github.com/drsapaev/final/pull/3846) | Registrar: снапшот очереди | 2 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3847](https://github.com/drsapaev/final/pull/3847) | Registrar: обновление списка | 1 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3848](https://github.com/drsapaev/final/pull/3848) | Registrar: таблица/статусы | 3 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3849](https://github.com/drsapaev/final/pull/3849) | Registrar: перенос визита | 2 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3853](https://github.com/drsapaev/final/pull/3853) | Cashier: защита от двойного submit | 2 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3854](https://github.com/drsapaev/final/pull/3854) | Cashier: терминальный статус/provider | 2 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3855](https://github.com/drsapaev/final/pull/3855) | Registrar: malformed queue | 1 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3856](https://github.com/drsapaev/final/pull/3856) | Queue: снятие выбора врача | 3 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3857](https://github.com/drsapaev/final/pull/3857) | Registrar: visit_id | 2 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3858](https://github.com/drsapaev/final/pull/3858) | CI: исправление теста даты | 1 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3864](https://github.com/drsapaev/final/pull/3864) | Cashier: серверная идемпотентность | 6 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3870](https://github.com/drsapaev/final/pull/3870) | Cashier: честные состояния загрузки | 4 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3876](https://github.com/drsapaev/final/pull/3876) | Cross-domain: P1 Registrar/Cashier/QR | 8 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3877](https://github.com/drsapaev/final/pull/3877) | Cross-domain: P2 Registrar/Cashier/QR | 11 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3878](https://github.com/drsapaev/final/pull/3878) | Cross-domain: оставшиеся исправления | 12 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3883](https://github.com/drsapaev/final/pull/3883) | Backup: backup/restore | 2 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3884](https://github.com/drsapaev/final/pull/3884) | QR: realtime/board | 5 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3889](https://github.com/drsapaev/final/pull/3889) | Backup: rehearsal/rollback | 1 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3890](https://github.com/drsapaev/final/pull/3890) | Backup: DR drill | 2 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3893](https://github.com/drsapaev/final/pull/3893) | EMR: concurrent create/template | 1 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3899](https://github.com/drsapaev/final/pull/3899) | QR: legacy join | 1 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3917](https://github.com/drsapaev/final/pull/3917) | Lab: тренд/идентичность | 2 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |
| [#3918](https://github.com/drsapaev/final/pull/3918) | Lab: guard/auth/UX | 7 | Нет содержательного итогового текста GitHub Review; повторное ревью требуется |

### Priority sequence for independent deep re-review

1. **P1 / financial correctness:** #3864 idempotency (RETRO-FIN-001); additionally #3814, #3853, #3870 and #3876–#3878 for cross-domain payment/refund server/client contracts. Must verify different-payload replay and audit boundaries; only synthetic PG/tests.
2. **P1 / EMR or protected information:** #3893 concurrent EMR create; #3876–#3878 cross-patient queue/registration actions; #3917 longitudinal lab report identity. Confirm patient/visit binding, row_version and late callback ownership.
3. **P1 / backup and recoverability:** #3883, #3889, #3890; use disposable archives/PostgreSQL and explicit negative tests before considering any DR 'pass'.
4. **P2 / navigation and queue integrity:** #3918 (RETRO-LAB-001), #3899, #3884, #3855–#3857; verify browser pop/reconnect/cancellation and server-authoritative identifiers.
5. **P2 / UI and reporting:** remaining registrar/cashier fix batches #3825–#3827, #3838–#3849, #3854; verify historical-ledger IDs, visible states, and correctness after async failures.

## Review already recorded (21 merged `fix` PRs)

The following fixes have a substantive GitHub Review submission recorded; **not all reviews were after the final push**. #3902/#3905/#3907/#3909 found additional issues that were later addressed in #3915; #3916 found two issues subsequently addressed in #3917. These fix-chain edges are not duplicate open vulnerabilities by themselves:

[#3804](https://github.com/drsapaev/final/pull/3804), [#3809](https://github.com/drsapaev/final/pull/3809), [#3821](https://github.com/drsapaev/final/pull/3821), [#3828](https://github.com/drsapaev/final/pull/3828), [#3829](https://github.com/drsapaev/final/pull/3829), [#3851](https://github.com/drsapaev/final/pull/3851), [#3888](https://github.com/drsapaev/final/pull/3888), [#3900](https://github.com/drsapaev/final/pull/3900), [#3901](https://github.com/drsapaev/final/pull/3901), [#3902](https://github.com/drsapaev/final/pull/3902), [#3903](https://github.com/drsapaev/final/pull/3903), [#3904](https://github.com/drsapaev/final/pull/3904), [#3905](https://github.com/drsapaev/final/pull/3905), [#3906](https://github.com/drsapaev/final/pull/3906), [#3907](https://github.com/drsapaev/final/pull/3907), [#3908](https://github.com/drsapaev/final/pull/3908), [#3909](https://github.com/drsapaev/final/pull/3909), [#3913](https://github.com/drsapaev/final/pull/3913), [#3914](https://github.com/drsapaev/final/pull/3914), [#3915](https://github.com/drsapaev/final/pull/3915), [#3916](https://github.com/drsapaev/final/pull/3916).

**Not-merged fix attempts (exclude from shipped count):** [#3885](https://github.com/drsapaev/final/pull/3885), [#3896](https://github.com/drsapaev/final/pull/3896), [#3919](https://github.com/drsapaev/final/pull/3919). #3919 duplicates the already-merged #3918. An open/recent search must not silently inflate remediation totals with these closed branches.

## Review/merge acceptance criteria for the NEXT repair PRs

- Fail-first regression demonstrates the issue on a pinned pre-fix SHA; test turns green after narrowly scoped change. Capture actual executed commands, CI run IDs and a final-head SHA.
- Independent code review on the **final changed commit**, not only a review receipt; identify P0/P1/P2 and resolve/rebut each inline finding with code/test evidence. Formal GitHub Review presence alone is insufficient.
- For finance, clinical, auth, queue, API contracts, backup/restore: run the mandatory `AGENTS.md` execution gate before changing source; verify PostgreSQL constraints/locks as needed. No real payments, patients, prod archives or unapproved writes.
- Update the corresponding original ledger **by finding ID**, with links to fix/test/review evidence. Keep `SOURCE-OBSERVED`, `REPRO-PENDING`, `FIXED-VERIFIED`, `CLOSED BY OPERATOR EVIDENCE`, and `NOT-REVIEWED` distinct.
- Do not merge this **documentation-only** retrospective as proof of code correctness. This file is a tracking artifact to coordinate subsequent narrow repair/review work.

## Stop point

The authorized outcome of this PR is **one newly added audit document only**. No source/tests/config changes, no production access, no merge/deploy, and no ungrounded assertion that the 33 reviewed-by-inventory fixes are individually correct. Follow-up source changes belong to separate scoped implementation PRs.
