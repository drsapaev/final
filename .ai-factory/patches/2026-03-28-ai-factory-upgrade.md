# Patch: AI Factory upgraded to upstream v2.8.1

**Date:** 2026-03-28

## Context

Upstream AI Factory was behind the local installation. The currently published release is `v2.8.1`, while the workspace still reflected `2.1.0`.

## Changes

- Synced the installed AI Factory skills from upstream `v2.8.1` into `.codex/skills/`
- Added new upstream skills:
  - `.codex/skills/aif-explore/`
  - `.codex/skills/aif-reference/`
- Updated `.ai-factory.json` to `2.8.1`
- Added project-specific skill-context overrides in `.ai-factory/skill-context/` so core AI Factory skills pick up the clinic repo conventions automatically
- Added the local `aif-deploy` skill-context override so deployment guidance also follows the current clinic runtime and release gates
- Expanded the utility skill-context set with `aif-best-practices`, `aif-loop`, and `aif-skill-generator`
- Added reliability-gate and docs context overrides for `aif-grounded` and `aif-docs`
- Cleaned active docs and context files to remove stale `8000` port references and SQLite-first wording from live operational guidance
- Aligned backend example/config files (`backend/.env.example`, `backend/env_setup_guide.md`, `backend/setup_env.py`) to the current Postgres/18000 contour
- Aligned backend runtime defaults (`backend/app/core/config.py`, `backend/app/db/session.py`, `backend/alembic.ini`) to the current Postgres/18000 contour
- Kept the local `aif-deploy` skill in place because it is present in the workspace but not in upstream AI Factory

## Verification

- Confirmed upstream latest release is `2.8.1`
- Compared local installed skills against upstream and added the missing upstream skills
- Added shared and skill-specific project context files for the main workflow skills
- Added a local deployment context override for `aif-deploy`
- Added utility skill overrides for best-practices, loop iteration, and skill generation workflows
- Added grounded-answer and docs-maintenance overrides for the remaining utility skills
- Swept the active docs set to replace legacy `8000` defaults and SQLite-first language with the current Postgres/18000 contour
- Aligned backend bootstrap examples and generators with the current Postgres/18000 contour
- Aligned backend runtime fallback/default behavior with the current Postgres/18000 contour
- Confirmed the local skill inventory now matches the upgraded release plus the existing local `aif-deploy` extension

## Notes

This upgrade mainly affects agent workflow skills and context-handling behavior. The project-specific `.ai-factory/` content was left intact.
