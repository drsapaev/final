# W2D Backend Entrypoint Support-File Verification Plan

Scope:

- verify `ops/backend.entrypoint.sh` against current backend config, env
  templates, and production-facing docs
- allow only a tiny support-file fix if the startup fallback is provably out of
  sync
- keep `create_all` and auto-admin behavior as findings unless a separate
  startup-semantics plan is opened

Evidence targets:

- `ops/backend.entrypoint.sh`
- `backend/app/core/config.py`
- `backend/app/db/session.py`
- `backend/.env.example`
- `ops/.env.example`
- `ops/README.md`
- `backend/SETUP_PRODUCTION.md`
- `backend/PRODUCTION_SETUP_SUMMARY.md`

Expected outcome:

- entrypoint fallback path aligned to the current backend env/config story
- explicit `/data` override wording preserved in ops docs/templates
- next honest follow-up shifted to a plan-gated startup semantics review
