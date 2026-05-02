# `aif-skill-generator` Context

Read `../common/SKILL.md` first.

## Project-Specific Notes

- Skills generated for this repo should be small, single-purpose, and wired to the clinic stack and AI Factory workflow conventions.
- If a generated skill is intended for use in this repo, include a short project-context hook that reads `.ai-factory/skill-context/<skill>/SKILL.md` when present.
- Use the repo's active contour in generated examples and docs: backend `18000`, frontend `5173`/`18080`, staging Postgres `55432`.
- Avoid generating SQLite-first, hardcoded-localhost, or port-8000 examples for this repo.
- For skills that touch live UI or persistence, include focused verification steps such as targeted tests or browser smoke checks.
- Keep security-sensitive generated skills aligned with prompt-injection scanning and least-privilege behavior.

