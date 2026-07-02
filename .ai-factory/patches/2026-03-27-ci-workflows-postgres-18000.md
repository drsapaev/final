# CI workflows/docs sweep: Postgres-first + `18000`

## Summary
- Updated GitHub Actions workflows to use backend `18000` instead of the legacy port.
- Replaced legacy CI examples with Postgres-first configuration and service containers.
- Kept the main CI pipeline aligned with the backend startup scripts and current Postgres runtime.

## Files Updated
- `.github/workflows/ci-cd-unified.yml`
- `.github/workflows/load-testing.yml`
- `.github/workflows/monitoring.yml`
- `README-CI-CD.md`
- `CI-CD-README.md`
- `.ai-factory/logs/PANEL_QA_IMPLEMENTATION_STATUS.md`

## Verification
- Search sweep found no standalone legacy port or database references in the updated CI/workflow/docs surface.
- `ci-cd-unified.yml` now uses `18000` in health checks, load-test base URL, and ZAP scan target.
- `load-testing.yml` and `monitoring.yml` now use Postgres service containers and `postgresql+psycopg://clinic:clinicpwd@localhost:5432/clinicdb`.

## Notes
- This cleanup stays scoped to CI/workflow/docs surfaces; older backend maintenance scripts that intentionally reference `clinic.db` were left untouched.
