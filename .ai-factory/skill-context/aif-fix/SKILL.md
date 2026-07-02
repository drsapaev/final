# `aif-fix` Context

Read `../common/SKILL.md` first.

## Project-Specific Notes

- Reproduce against the real local stack first: backend `18000`, frontend `5173`, and staging Postgres `55432` when relevant.
- Prefer a narrow fix plus a regression test over a broad refactor.
- If the bug is caused by normalization drift, fix the canonical server-side path and add coverage for the normalized form.
- If the issue affects a live UI flow, verify the before/after behavior and note whether the UI still needs a reload.
- If the root cause is a stale port, CORS, or docs mismatch, update the corresponding config or docs in the same patch.

