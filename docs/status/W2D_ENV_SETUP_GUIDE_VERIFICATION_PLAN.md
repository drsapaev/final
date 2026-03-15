# W2D Env Setup Guide Verification Plan

Scope:

- verify `backend/env_setup_guide.md` against `backend/.env.example`,
  `ops/.env.example`, and current backend config
- keep the slice docs-only
- preserve the file as a short env entry guide, not a full setup manual

Evidence targets:

- `backend/env_setup_guide.md`
- `backend/.env.example`
- `ops/.env.example`
- `backend/app/core/config.py`

Expected outcome:

- the guide becomes a current dev-first env entrypoint
- stale inline env examples and dead links are removed or downgraded
- the next low-risk target shifts to `backend/.env.example`
