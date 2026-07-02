# `aif-best-practices` Context

Read `../common/SKILL.md` first.

## Project-Specific Notes

- Prefer advice that matches the clinic stack: FastAPI + SQLAlchemy + Pydantic v2 on the backend, React 18 + Vite on the frontend.
- In backend examples, keep the `endpoint -> service -> repository -> DB` split and avoid direct ORM/business logic in endpoints.
- In frontend examples, keep data access in hooks/services and preserve role-specific UI modules and existing component boundaries.
- Treat audit logging, RBAC, normalization, and live-state persistence as first-class best-practice concerns, not edge cases.
- When reviewing or refactoring, prioritize stale ports, hardcoded URLs, SQLite drift, and missing tests for queue/billing/settings flows before stylistic nits.
- Use the repository's existing naming and module patterns in examples instead of introducing alternate stacks or abstractions.

