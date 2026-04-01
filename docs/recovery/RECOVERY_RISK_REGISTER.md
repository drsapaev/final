# Recovery Risk Register

| risk | conflict area | impact | mitigation |
|---|---|---|---|
| Merge conflict drift in runtime endpoints | `backend/app/api/v1/endpoints/messages.py`, `services.py`, `visits.py` | Could reintroduce stale service/repository assumptions. | Prefer `REIMPLEMENT` from current main; do not merge whole wave branches. |
| Notification contract divergence | `frontend/src/services/notify.js` vs precursor adapter files | Old panel-level alert/toast paths can reappear if precursor branches are merged blindly. | Keep a single notify adapter; port only the adapter idea, not the old path. |
| Queue SSOT drift | `docs/QUEUE_SYSTEM_ARCHITECTURE.md` and queue-wave branches | Historical queue docs can be mistaken for active architecture. | Refresh the SSOT doc and archive the historical implementation notes. |
| Binary snapshot contamination | `feat/macos-ui-refactor` / `backend/clinic.db` | Binary DB snapshots are not recoverable code artifacts and can hide state drift. | Drop the branch outright. |
| Legacy dotfile / config churn | `123` branch | Brings `.claude`, `.cursor`, `.gitattributes`, and legacy queue deletion churn. | Drop and keep only the history as evidence. |
| Docs vs code mismatch | `.ai-factory` plans/logs, queue reports, notification architecture docs | Docs may describe a pre-main truth and mislead future agents. | Classify each doc as update / archive / keep-current before reuse. |
| Dependency bump regressions | Dependabot refs | Workflow or backend deps can break CI if applied out of order. | Cherry-pick one ref at a time and run the smallest relevant check set. |
| Cross-role leakage | Notifications / role-center paths | Notification history or inbox scope can leak across recipients if scoped loading is not preserved. | Keep recipient-scoped API calls and server-side validation. |

## Highest-Risk Families
- `codex/startup-operator-first-hardening`
- `codex/w2a-service-repository-*`
- `codex/w2c-*`
- `codex/post-w2c-*`
- `wip-jules-*`
- `123`
- `feat/macos-ui-refactor`

## Lowest-Risk Recovery Candidates
- `dependabot/github_actions/actions/checkout-6`
- `dependabot/github_actions/actions/setup-node-6`
- `dependabot/github_actions/actions/setup-python-6`
- `origin/dependabot/github_actions/actions/upload-artifact-7`
- `origin/dependabot/github_actions/docker/build-push-action-7`
- `origin/dependabot/pip/backend/alembic-gte-1.13-and-lt-1.19`
- `origin/dependabot/pip/backend/fastapi-gte-0.121-and-lt-0.136`
- `origin/dependabot/pip/backend/pydantic-gte-2.7-and-lt-2.13`
- `origin/dependabot/pip/backend/uvicorn-standard--gte-0.29-and-lt-0.43`
- `origin/dependabot/pip/backend/redis-gte-5.0-and-lt-8.0`
