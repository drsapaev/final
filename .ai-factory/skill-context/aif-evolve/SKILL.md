# `aif-evolve` Context

Read `../common/SKILL.md` first.

## Project-Specific Notes

- Promote recurring local patterns into skill-context before rewriting large skill files.
- For this repo, recurring drift points are ports, CORS, Postgres-first data flow, live UI persistence, and normalization of user input.
- Keep new rules tied to actual file paths or patch history.
- Prefer minimal project overrides that complement the upstream skill rather than replacing it.

