# W2D Backend Env Example Verification Plan

Scope:

- verify `backend/.env.example` against current backend config and neighboring
  env docs
- keep the slice bounded to template/comment-level corrections
- avoid turning the env template into a large setup manual

Evidence targets:

- `backend/.env.example`
- `backend/app/core/config.py`
- `backend/env_setup_guide.md`
- `ops/.env.example`

Expected outcome:

- stale split Postgres comment path removed
- current backend template keys/comments aligned with current config
- the next honest follow-up shifts to a plan-gated audit of
  `ops/docker-compose.yml`
