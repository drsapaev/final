# `aif-review` Context

Read `../common/SKILL.md` first.

## Project-Specific Notes

- Prioritize boundary, auth/RBAC, schema drift, and live-state regressions.
- Look for raw ORM access in endpoints, hardcoded backend URLs, stale CORS/origin lists, and missing Alembic migrations.
- For frontend review, check that save/refund/queue updates behave as live state when that is the feature intent.
- If the review touches AI Factory context files, ensure the changes are minimal and traceable to the project facts or patches.
- Report findings first with file and line references.

