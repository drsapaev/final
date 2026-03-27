# `aif-deploy` Context

Read `../common/SKILL.md` first.

## Project-Specific Notes

- Treat deployment as approval-gated. Do not auto-deploy without an explicit release step.
- Verify the current clinic runtime and release gates before changing deployment steps.
- Use backend `18000`, frontend `5173/18080`, and staging `55432` as the known local/staging contour when documenting or validating release prep.
- Keep deployment notes aligned with the current Postgres-first architecture and the repo's CI/workflow gates.

