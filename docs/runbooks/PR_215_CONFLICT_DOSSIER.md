# PR #215 Conflict Dossier

Generated: 2026-05-02

## Goal

Prepare the replacement parent PR #215 for refresh against current `main` without touching the active workspace.

## Isolation

Conflict analysis was done in a temporary clone under `%TEMP%`, not in `C:\final`.

## Attempted Refresh

Branch tested:

- Base: current `origin/main`
- Source: `origin/codex/w2a-root-parent-replacement-20260502`
- Test branch: `codex/w2a-root-parent-refresh-20260502` in temp clone only

Commits to replay from #215 source branch:

- `b49f1c3974d244f563f244425a9392ad3b15871b`
- `c560b0796540a25da105b263d853ff17b4325648`

## Result

The first cherry-pick conflicts.

Conflict commit:

- `b49f1c3974d244f563f244425a9392ad3b15871b`
- Message: `refactor(messages): enforce router-service-repository boundary for W2A`

Conflicted file:

- `backend/app/api/v1/endpoints/messages.py`

Conflict shape:

- Current `main` keeps the large existing `messages.py` router implementation, including voice message endpoints and file serving.
- #215 wants to replace that file with a minimal service-first router wrapper:

```python
"""Service-first router wiring for messaging endpoints."""

from app.services.messages_api_service import router
```

## Interpretation

This is not a trivial text conflict. It is an ownership/architecture conflict:

- If we take #215 as-is, we may remove message router endpoints that current `main` still owns in `messages.py`.
- If we keep current `main`, the W2A service/repository root work is not restored.
- The safe fix requires reviewing whether `app.services.messages_api_service` currently contains every route and behavior from the current `messages.py`, especially voice/file endpoints.

## Recommendation

Do not auto-resolve this conflict.

Next safe step:

1. Inspect current `backend/app/api/v1/endpoints/messages.py` and `backend/app/services/messages_api_service.py` in a dedicated conflict-resolution branch.
2. Prove route parity before replacing the router implementation.
3. If parity is incomplete, port only the safe service-boundary pieces or split #215 into smaller replacement PRs.
4. Keep #215 labeled `blocked:conflicts` until this is resolved.

## Status

No push was made from the temp clone.
No merge was performed.
No descendant PR was retargeted.
