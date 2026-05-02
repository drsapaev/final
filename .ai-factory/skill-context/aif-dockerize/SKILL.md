# `aif-dockerize` Context

Read `../common/SKILL.md` first.

## Project-Specific Notes

- Keep Docker and compose guidance aligned with the clinic app's FastAPI, React/Vite, and PostgreSQL stack.
- Use backend `18000`, frontend `5173`, and staging `55432` when describing runtime ports.
- Do not add SQLite as an operational container target.
- If a container or compose change affects dev startup, update the matching docs and env samples.

