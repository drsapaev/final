# `aif-ci` Context

Read `../common/SKILL.md` first.

## Project-Specific Notes

- Align CI with the current clinic runtime, especially backend `18000` and Postgres-first service containers.
- Do not reintroduce SQLite-based CI assumptions.
- Keep workflow checks explicit for lint, tests, security, and any browser/load gates already used by the repo.
- If CI docs or workflows mention ports, ensure they match the current staging and local contour.

