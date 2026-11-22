# Continued Code Review — group 89: Telegram proposed-fix Markdown and post-commit acknowledgement gaps

**Review date:** 2026-11-15 (Asia/Tashkent). **Mode:** source-backed review/documentation only; no protected-source edits. **Current main:** [`b142a30dc433dbd2486a421f1b8ba1c0a5cabb9a`](https://github.com/drsapaev/final/commit/b142a30dc433dbd2486a421f1b8ba1c0a5cabb9a). **Open fix PR:** [#4076](https://github.com/drsapaev/final/pull/4076), exact reviewed head `a775c70b368f2fc1cbb21d12a3febf40e69e3033` (not merged). **Existing Draft audit:** [#4059](https://github.com/drsapaev/final/pull/4059), continuing groups 47–88. **Owner issue:** [#4063](https://github.com/drsapaev/final/issues/4063), 404 unique IDs, 38 checked historical source fixes, 366 unchecked requiring individual adjudication; **none** of these 366 can be assumed unresolved just from the checkbox.

Read current root `AGENTS.md`, `.agents/skills/code-security/SKILL.md`, the actual Telegram backend handler and notification sender at exact #4076 head, `backend/tests/integration/test_notifytg_plane.py`, and existing group88 addendum. No local checkout or PowerShell runner was available in this review environment. No claim of executable test or gate evidence.

## Gap A — P2 conditional: lab notification still sends unescaped Markdown (`NOTIFYTGMARKDOWN-BE-001`)

- **Source at proposed fix head:** [`bot.py:513–525`](https://github.com/drsapaev/final/blob/a775c70b368f2fc1cbb21d12a3febf40e69e3033/backend/app/services/telegram/bot.py#L513-L525) builds lab message with raw `results_info.get('test_name')` and `results_info.get('date')`. The new helper `_md_escape` is used for doctor/date/time in appointment reminders, but **not in this lab template**.
- The shared [`send_notification` uses `parse_mode="Markdown"`](https://github.com/drsapaev/final/blob/a775c70b368f2fc1cbb21d12a3febf40e69e3033/backend/app/services/telegram/bot.py#L449-L470). Lab values containing `_`, `*` or `[` may break Telegram legacy Markdown parsing or render incorrectly, leading to a failed provider call or distorted content.
- **Test gap:** [`test_notifytg_plane.py`](https://github.com/drsapaev/final/blob/a775c70b368f2fc1cbb21d12a3febf40e69e3033/backend/tests/integration/test_notifytg_plane.py) tests legacy Markdown in invitation and callback routing but has no lab-field Markdown test.
- **Proposed fail-first regression:** capture the outbound message via a monkeypatched `send_notification` when `send_lab_results_ready(1, {"test_name":"SYN_lab_[x]*", "date":"2026_11_15"})` is called; assert escaped lab fields in text and expected send result. Assert no raw user fields are logged on a simulated provider parse failure. Keep synthetic values only.
- **Disposition:** incomplete proposed coverage of existing unchecked `NOTIFYTGMARKDOWN-BE-001`; do not create a duplicate issue ID, do not claim observed provider failure.

## Gap B — P2 conditional: committed status is followed by false failure ACK if Telegram edit fails (`NOTIFYTGREMINDCB-BE-001`)

- **Source at proposed fix head:** [`bot.py:342–363`](https://github.com/drsapaev/final/blob/a775c70b368f2fc1cbb21d12a3febf40e69e3033/backend/app/services/telegram/bot.py#L342-L363) calls `db.commit()` before the awaited `callback.message.edit_text()`. Any edit exception reaches the broad `except` handler, which tells the patient «Произошла ошибка» while the status has already changed in the DB.
- **Consequence:** user may retry an already effected status change. This is separate from *transport delivery false-ACK*: a post-commit UI failure is reported as a mutation failure.
- **Proposed fail-first regression:** synthetic, correctly linked patient and permitted appointment; force `callback.message.edit_text` to raise after successful DB commit. Assert appointment change persists, Telegram callback receives truthful success/processed message, no repeated mutation, and logging contains no patient/chat identifiers.
- **Remediation boundary:** separate DB status-mutation failure from best-effort post-commit UI edit; ACK the committed outcome. Do not work around the unresolved P1 financial-status or P2 NO_SHOW terminal-state guards. Any new persisted RSVP contract needs owner decision and DB/contract gate first.
- **Disposition:** candidate completeness issue in *unmerged* `NOTIFYTGREMINDCB-BE-001` implementation, **not a new main finding**.

## Existing group88 blockers remain open, not newly counted

1. **P1 conditional:** `confirm_<id>` writes literal `status="confirmed"` which maps to `PAID` without checking payment SSOT; clinical/payment product policy not yet resolved.
2. **P2:** `cancel_<id>` can rewrite terminal `no_show` to `cancelled`, bypassing `can_transition_status`.
3. **P2 incomplete `NOTIFYTGFALSEACK-BE-001`:** `POST /api/v1/telegram/bot/send-lab-notification` discards returned False and still returns 200 success.

**Direct action:** posted [follow-up Code Review comment on #4076](https://github.com/drsapaev/final/pull/4076#issuecomment-6888149009) with both new gaps, test contracts and merge-block status.

## Group89 ledger / verification boundaries

| Item | Before | Group89 | After |
| --- | ---: | ---: | ---: |
| Owner #4063 unique main-source candidate IDs | 404 | +0 | **404** |
| Owner checkbox-verified historical fixes | 38 | +0 | **38** |
| Unchecked requiring evidence/disposition | 366 | +0 | **366** |
| Newly merged and independently verified source fixes | 0 | +0 | **0** |
| New exact-head #4076 review gaps | 3 prior group88 | +2 distinct | **5 blockers/gaps** |

#4076 remains **OPEN/unmerged**. `run_agent_gate.ps1` was **NOT RUN** by this auditor and is explicitly marked **NOT RUN** in the source-fix PR; do not bypass mandatory gated Telegram/clinical changes. No `pytest`, live Telegram API, production database, patient data, merge, or deployment was executed in this review. CI cannot prove these missing negative tests by itself. The fixing agent must correct both this group's gaps **and** group88 blockers in the appropriate source fix PR, obtain mandated gate evidence/authorized override, run fail-first negative tests and exact-head checks. After every real fixing action report in this **same audit #4059** as directed by owner, with #4063 IDs, real merged-main outcomes, SHAs, tests, gate, and remaining blockers.
