# Wave 1 Safe Follow-Up Tasks

Date: 2026-03-06

## Wave 1.5 Execution Update

| ID | Title | Why now | Scope guard |
|---|---|---|---|
| FUP-01 | Fix `TwoFactorManager` CI blocker | done in Wave 1.5 (`W15-T1`) | test scope only |
| FUP-02 | Stabilize `test_role_routing.py` signal | done in Wave 1.5 (`W15-T2`) | deterministic test wrapper only |
| FUP-05 | Docs normalization for high-risk claims | partial in Wave 1.5 (`W15-T3`) | docs-only; broad sweep deferred |
| FUP-03 | Security slice A (frontend deps) | partial in Wave 1.5 (`W15-T4`) | non-major safe updates only |
| FUP-04 | Security slice B (bandit hardening) | pending human review in Wave 1.5 (`W15-T5`) | protected payment paths not auto-edited |

## Recommended Next 5 Tasks (Post Wave 1.5)

| ID | Title | Why now | Scope guard |
|---|---|---|---|
| FUP-06 | PDF dependency major-remediation (`jspdf` 4.2.x) | Remaining critical vuln in frontend audit | dedicated slice + PDF regression checks |
| FUP-07 | Resolve Storybook 8.6.17 patch upgrade conflicts | Remaining high findings include storybook advisories | devDependencies only; no app logic change |
| FUP-08 | Payment signature hashing review (`Click` + webhook) | Remaining `B324` high in protected payment files | **mandatory human review** |
| FUP-09 | Jinja `B701` hardening plan (print/pdf/ai templates) | High findings concentrated across template renderers | staged rollout with output-compat tests |
| FUP-10 | Docs cleanup sweep for legacy/archive claims | Wave 1.5 normalized only high-visibility docs | docs-only batch, bounded diff |

## Wave 1.75 Gate Update

- Gate decision: `NOT_READY_FOR_WAVE2` (see `docs/status/WAVE2_GATE_DECISION.md`).
- New blocking signals:
  - backend root `pytest -q` instability (`test_cart_direct.py` import-time `SystemExit`)
  - no fresh green unified `main` run proving post-W1.5 stabilization
  - protected-zone security items still pending human review
  - `jspdf` critical risk mitigated temporarily, not remediated

## Recommended Next 5 Tasks (Post Wave 1.75)

| ID | Title | Why now | Scope guard |
|---|---|---|---|
| FUP-11 | Normalize backend root test entrypoint (`pytest -q`) | Current gate blocked by root collection side effects | tests/harness only; no auth/payment logic changes |
| FUP-12 | Re-run unified CI on a bounded stabilization PR and capture green evidence | Need fresh objective CI proof on current code state | no code churn beyond stabilization patch scope |
| FUP-13 | Human-reviewed payment signature plan (`B324`) | Protected payment findings remain high-risk | **mandatory human review** |
| FUP-14 | Human-reviewed template autoescape rollout (`B701`) | Print/PDF/template hardening remains unresolved | staged changes + snapshot/output compatibility tests |
| FUP-15 | Dedicated `jspdf` major-upgrade validation slice | Critical dependency unresolved | focused PDF regression suite + rollback plan |

## Deferred by Design in Wave 1

- Any dependency upgrade execution.
- Any protected-domain behavior rewrite (auth/payment/queue/EMR).
- Any broad docs sweep beyond Wave 1 reports and trackers.
