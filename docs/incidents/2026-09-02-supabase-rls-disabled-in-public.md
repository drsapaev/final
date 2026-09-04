# Incident 2026-09-02: Supabase `rls_disabled_in_public` — out-of-band tables without RLS

- **Severity**: P1 (security exposure, medical data platform)
- **Detected by**: Supabase Advisor email to the operator ("Action required: security vulnerabilities detected in your projects", project `riwgarlpbingmqbwyuds`)
- **Status**: CLOSED — exposure closed, ownership restored, CI guardrail merged; **one live recurrence the same day** (see "Recurrence") — the process gap is still active while sessions bypass Alembic.

## Timeline (all 2026, local +05)

| When | What |
|---|---|
| 2026-08-18 | `0046_enable_rls` sweep applied manually to prod; RLS model live (owner `postgres` bypasses; deny-all for `anon`/`authenticated`; 0 policies) |
| ~Aug 18 – Sep 1 | `salary_history`, `salary_payments` created on prod **out-of-band** (ad-hoc `Base.metadata` DDL; `relfrozenxid` 1374 vs the Aug-18 cluster at 1177) — no Alembic revision, no RLS |
| 09-02 ~14:00 | Operator forwards Supabase Advisor alert |
| 09-02 ~15:00 | Read-only prod inventory: **2 of 173 public tables RLS-off** (`salary_history`, `salary_payments`); chain-vs-prod diff (171 chain tables + 2 = 173) pins the mechanism |
| 09-02 | `0050_enable_rls_sweep` (#3006): idempotent re-sweep; validated on disposable PG (171/171); applied to prod → **173/173 RLS ON**; app healthy |
| 09-02 | Root cause hardened: `0051_salary_tables_adoption` (#3008) adopts the tables (inspect-then-create; fresh-install DDL mirrors live schema 1:1) + `models/__init__.py` registry import (the enabler: unregistered models are invisible to Alembic autogenerate) |
| 09-02 | CI guardrail (#3009): after `alembic upgrade head` on the disposable PostgreSQL in the Backend тесты job, `ops/scripts/check_public_rls.py` fails the build if ANY public table has `relrowsecurity = false` |
| 09-02 ~19:30 | **Live recurrence**: `public.medical_specialties` found RLS-off (relfrozenxid 1670 — created within hours, again with no migration/model in the repo). Exposure closed immediately (`ALTER TABLE … ENABLE ROW LEVEL SECURITY`; owner-role access unaffected). Table itself left for its creating session to own. |

## Root cause

1. **Enabler (code)**: salary models were never imported in `backend/app/models/__init__.py` → invisible to `Base.metadata` and Alembic autogenerate → the merged salary feature shipped for months without a creating migration.
2. **Mechanism (process)**: a session ran ad-hoc `Base.metadata`-style DDL **directly against production** to unblock itself, instead of adding an Alembic revision. The 0046 sweep predates the tables, so nothing re-enabled RLS on them.
3. **Detection gap**: nothing verified the RLS invariant after schema changes; the first detector was a vendor email days later.

## Closing evidence (live production)

- After `0050` + `0051`: `alembic_version = 0051_salary_tables_adoption`; adoption log lines `public.salary_history already exists — skipping CREATE` / same for `salary_payments`; **173/173 public tables `relrowsecurity = true`, 0 off**; `SELECT count(*) FROM salary_history` under the owner role works (0 rows); `/api/v1/health` → 200 `{ok, db: ok}`.
- After the recurrence fix: **174/174 RLS ON** (includes `medical_specialties`), health 200.
- Supabase Advisor: re-scan should report zero `rls_disabled_in_public` findings (DB-level invariant proven above; dashboard confirmation pending the next advisor pass).

## Prevention (merged)

- `0051` adoption pattern + models registry import (autogenerate sees everything registered).
- CI: `ops/scripts/check_public_rls.py` in the Backend тесты job — any chain-created table without RLS fails CI **before merge** (locally verified both ways: 171/171 pass; DISABLE RLS on `patients` → FAIL naming the table).
- Rule (AGENTS.md, DB Guardrails): never create/alter production tables via ad-hoc SQL; every schema change ships as an Alembic revision, and a creating revision must enable RLS.

## Open items

- `medical_specialties` (recurrence) still has **no owning migration/model** — the session that created it must adopt it (0051 pattern) or drop it; until then it is chain-invisible (the CI guard cannot see out-of-band tables — only live inventory can).
- ~~Audit trail for out-of-band DDL: consider a weekly cron~~ **DONE (2026-09-03)**: `ops/scripts/nightly_rls_inventory.ps1` runs the `check_public_rls.py` inventory against the live production database daily at 03:35 (Windows scheduled task `FinalClinic RLS Nightly Inventory` on the prod host) and raises a Sentry event on drift; log at `C:inal	oolsls_inventory.log`. The CI guard covers the chain; this covers the live DB.
