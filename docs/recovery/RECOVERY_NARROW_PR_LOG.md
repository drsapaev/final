# Recovery Narrow PR Log

## Branch Setup
- new_branch: `codex/recovery-main-final`
- base_commit: `959d457b8c1f9883a310f12b790c72e1dd4c1c19`
- worktree: `C:\final-narrow`
- source_contaminated_branch: `codex/recovery-main-execution`

## Imported Recovery Packet Material
- `a7bcfa6f` / `docs: add recovery audit reports`
- `98d9414b` / `docs: add execution-grade recovery packet`
- `e67eb409` / `chore(ci): bump docker build-push action to v7`
- `4227ea1a` / `chore(ci): bump upload-artifact action to v7`
- `be0ed21d` / `chore(backend): widen alembic constraint to <1.19`
- `b3f01259` / `chore(backend): widen fastapi constraint to <0.136`
- `df491cac` / `chore(backend): widen pydantic constraint to <2.13`
- `83b36971` / `chore(backend): widen uvicorn constraint to <0.43`
- `cdae8c79` / `chore(backend): widen redis constraint to <8.0`

## Explicitly Excluded From This New Branch
- PR `#144` contaminated runtime expansion
- `frontend/src/components/emr-v2/*`
- `frontend/src/pages/PatientPanel.jsx`
- `backend/app/services/*`
- `docs/status/*`
- all unrelated historical feature branches and wave content

## Safety Confirmation
- `main` was not modified.
- The new branch starts from clean current local `main`.
- No contaminated branch history was rewritten.
- No force-push or merge was used.
