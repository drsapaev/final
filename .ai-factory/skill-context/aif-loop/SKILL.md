# `aif-loop` Context

Read `../common/SKILL.md` first.

## Project-Specific Notes

- When the loop targets clinic artifacts, evaluate against the current runtime contour: backend `18000`, frontend `5173`, staging Postgres `55432`, and Vite proxy behavior.
- Use browser or local-stack evidence for user-facing flows, especially queue, cashier, display, settings, and payment state.
- Keep loop outputs tight and resume-friendly; prefer one narrow artifact per run instead of broad rewrite passes.
- Do not confuse `.ai-factory/evolution/` loop state with `.ai-factory/evolutions/` AI Factory evolution logs. They are separate artifacts.
- Prefer refinements that add missing verification, clarify ambiguous clinic behavior, or remove stale port/runtime assumptions.

