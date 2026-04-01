# Recovery Changeset Shortlist

## Rules Used
- Only items with a concrete gap in current main are listed.
- No broad feature branch passed the proof threshold here.
- The shortlist is intentionally limited to the lowest-risk recovery items.

| source branch | commit range or file slice | exact missing value in current main | proof that the gap is real | why not already covered by main | action | regression risk | required tests | priority | final status |
|---|---|---|---|---|---|---|---|---|
| `dependabot/github_actions/actions/checkout-6` | workflow-only branch slice | Candidate intended to move `actions/checkout` to `v6` | Execution triage found current `main` already on `v6` | Current `main` superseded the shortlist evidence | drop | low | direct workflow version inspection | P1 | `no-op / already in main` |
| `dependabot/github_actions/actions/setup-node-6` | workflow-only branch slice | Candidate intended to move `actions/setup-node` to `v6` | Execution triage found current `main` already on `v6` | Current `main` superseded the shortlist evidence | drop | low | direct workflow version inspection | P1 | `no-op / already in main` |
| `dependabot/github_actions/actions/setup-python-6` | workflow-only branch slice | Candidate intended to move `actions/setup-python` to `v6` | Execution triage found current `main` already on `v6` | Current `main` superseded the shortlist evidence | drop | low | direct workflow version inspection | P1 | `no-op / already in main` |
| `origin/dependabot/github_actions/actions/upload-artifact-7` | workflow-only branch slice | Mixed `upload-artifact` versions remained on current workflows | Current `main` still had `v4` / `v5` usage on the candidate-covered files | No equivalent `v7` normalization was present on current `main` | manual reapply | low | YAML parse of touched workflows; `git diff --check` | P1 | `done` |
| `origin/dependabot/github_actions/docker/build-push-action-7` | workflow-only branch slice | `docker/build-push-action` still pinned to `v6` in Docker build jobs | Current `main` still differed on the exact Docker build steps | No equivalent `v7` bump was present on current `main` | manual reapply | low | YAML parse of touched workflow; `git diff --check` | P1 | `done` |
| `origin/dependabot/pip/backend/alembic-gte-1.13-and-lt-1.19` | `backend/pyproject.toml` + `backend/requirements.txt` | Alembic upper bound was still `<1.18` | Current dependency manifests still carried the older bound | No equivalent constraints update was present on current `main` | manual reapply | low | backend import smoke; targeted pytest; `git diff --check` | P1 | `done` |
| `origin/dependabot/pip/backend/fastapi-gte-0.121-and-lt-0.136` | `backend/pyproject.toml` + `backend/requirements.txt` | FastAPI upper bound was still `<0.130` | Current dependency manifests still carried the older bound | No equivalent constraints update was present on current `main` | manual reapply | low | backend import smoke; targeted pytest; `git diff --check` | P1 | `done` |
| `origin/dependabot/pip/backend/pydantic-gte-2.7-and-lt-2.13` | `backend/pyproject.toml` + `backend/requirements.txt` | Pydantic upper bound was still `<2.12` | Current dependency manifests still carried the older bound | No equivalent constraints update was present on current `main` | manual reapply | low | backend import smoke; targeted pytest; `git diff --check` | P1 | `done` |
| `origin/dependabot/pip/backend/uvicorn-standard--gte-0.29-and-lt-0.43` | `backend/pyproject.toml` + `backend/requirements.txt` | Uvicorn upper bound was still `<0.39` | Current dependency manifests still carried the older bound | No equivalent constraints update was present on current `main` | manual reapply | low | backend import smoke; targeted pytest; `git diff --check` | P1 | `done` |
| `origin/dependabot/pip/backend/redis-gte-5.0-and-lt-8.0` | `backend/pyproject.toml` + `backend/requirements.txt` | Redis upper bound was still `<6.0` | Current dependency manifests still carried the older bound | No equivalent constraints update was present on current `main` | manual reapply | low | backend import smoke; targeted pytest; `git diff --check` | P1 | `done` |

## Exclusions
- No feature-branch item is included without a demonstrated gap in current main.
- That means the w2a, w2c, post-w2c, notification precursor, startup hardening, and wip-jules families stay out of the shortlist.
