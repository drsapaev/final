# Audit remediation registry (issue #4063)

Machine-readable register of all **323** code-review finding IDs tracked in
[issue #4063](https://github.com/drsapaev/final/issues/4063), plus the checker
that enforces the remediation rules mechanically.

## Files

| Path | Purpose |
| --- | --- |
| `docs/audit-registry/registry.json` | Per-ID entries: `id`, `priority`, `source`, `evidence`, `status`, `fix_pr`, `merge_sha`, `test_before`, `test_after`, `reviewer`, `date`, plus disposition fields (`alias_of`, `justification`, `root_cause`). |
| `tools/audit_registry/check_registry.py` | Standalone stdlib-only validator. |

## Statuses

`UNVERIFIED` · `CONFIRMED_OPEN` · `FIX_IN_PROGRESS` · `FIX_PROPOSED_DRAFT` ·
`FIXED_VERIFIED_ON_MAIN` · `DUPLICATE` · `REFUTED` · `OWNER_ACCEPTED_RISK`

## Enforced rules

1. **No silent loss / renaming** — `--issue-check` cross-checks the registry 1:1
   against the live `#4063` checklist. An ID present in the issue but missing
   from the registry (or vice versa) fails CI. New audit findings must be added
   to both.
2. **No double closing** — duplicate IDs fail validation, so a finding cannot
   be closed twice under different names.
3. **No unevidenced fixes** — `FIXED_VERIFIED_ON_MAIN` requires `fix_pr`
   (merged), `merge_sha`, `test_before`, `test_after`, `reviewer`, `date`.
   A draft PR, green docs CI, or a "fixed" comment is **not** sufficient.
4. **No unexplained dispositions** — `DUPLICATE` requires `alias_of`;
   `REFUTED` / `OWNER_ACCEPTED_RISK` require a concrete `justification`
   (test or source evidence; accepted risk additionally requires explicit
   owner sign-off recorded in the issue).
5. **Final closure gate** — `--final-closure` fails while any entry is
   `UNVERIFIED` / `CONFIRMED_OPEN` / `FIX_IN_PROGRESS` / `FIX_PROPOSED_DRAFT`.
   It runs only via `workflow_dispatch` so it blocks the *closure*, not the
   ongoing remediation work.

## Usage

```bash
python tools/audit_registry/check_registry.py                       # schema + evidence rules
python tools/audit_registry/check_registry.py --issue-check        # + 1:1 vs #4063 checklist
python tools/audit_registry/check_registry.py --issue-check --final-closure
```

## Updating the registry

- Change one status per commit, keep the evidence fields complete.
- When a fix PR merges: set `status=FIXED_VERIFIED_ON_MAIN`, fill `merge_sha`
  (the PR merge commit on `main`), `test_before`/`test_after` (the real RED→GREEN
  commands/results), `reviewer`, `date`, and tick the checkbox in `#4063`.
- Never delete an entry. Withdrawn/refuted findings stay with their disposition.
- Branch protection: once the owner approves this automation, make
  `audit-registry / registry-consistency` a Required status check; run
  `audit-registry / audit-final-closure` (dispatch, `final_closure=true`) as the
  last step before closing `#4063`.

## Current baseline (v1, generated 2026-11-13, revalidated on main `94d140f83`)

- `FIXED_VERIFIED_ON_MAIN`: **41** — 27 original `#3892` findings (fixes `#3903`/`#3908`,
  previously independently verified; spot-checked on 2026-11-13 that only scoped
  `#4024` touched the dental FE dirs since the verification anchor `3afe005c7d`)
  + 14 IDs fixed by merged remediation PRs `#4035`, `#4044`, `#4046`, `#4048`,
  `#4050`, `#3976`, `#3977` (merge SHAs + test evidence in the registry).
- `FIX_PROPOSED_DRAFT`: **26** — the 24 `#4054` platform-series findings plus
  `DENTPRICE-BE-001` / `NOTIFYDENTTELEHTML-BE-001`, addressed by draft `#4060`
  (head `400ff2e4d`). Two blockers are on record in that PR (protected
  lab-dirty-guard e2e chat-dialog contract; four legacy `send_telegram_message`
  callers — dental ×2, lab ×2 — silently failing without `db`). These stay
  unchecked until merged and verified on `main`.
- `UNVERIFIED`: **256** — per-ID adjudication continues by priority
  (P0/P1 security/access/clinical/financial first).
