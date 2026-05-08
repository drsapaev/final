# PR #215 Route Parity Review

Generated: 2026-05-02

## Scope

Compared current `main` messaging router behavior against the service-first router target used by PR #215.

Files compared from Git refs in isolated temp clone:

- `origin/main:backend/app/api/v1/endpoints/messages.py`
- `origin/main:backend/app/services/messages_api_service.py`
- `origin/codex/w2a-root-parent-replacement-20260502:backend/app/api/v1/endpoints/messages.py`
- `origin/codex/w2a-root-parent-replacement-20260502:backend/app/services/messages_api_service.py`

## Route Count Result

Route-level parity is present: both current endpoint router and service router expose 12 routes.

| Method | Path | Service route present |
| --- | --- | --- |
| POST | `/send` | yes |
| GET | `/conversations` | yes |
| GET | `/conversation/{user_id}` | yes |
| GET | `/unread` | yes |
| PATCH | `/{message_id}/read` | yes |
| DELETE | `/{message_id}` | yes |
| POST | `/{message_id}/reactions` | yes |
| GET | `/users/available` | yes |
| POST | `/send-voice` | yes |
| GET | `/voice/{message_id}/stream` | yes |
| POST | `/upload` | yes |
| GET | `/download/{filename}` | yes |

## Blocking Finding

Route parity is not enough. Behavior/security parity fails for `GET /download/{filename}`.

Current `main` endpoint implementation:

- sanitizes `filename` with `os.path.basename(filename)`
- receives `db: Session = Depends(get_db)`
- looks up `FileModel` and related `Message`
- denies access unless current user is sender or recipient
- returns `403` when the file is not linked to an authorized message

Service router implementation:

- does not receive `db`
- does not look up `FileModel` or `Message`
- does not check sender/recipient authorization
- only checks whether `uploads/chat/<filename>` exists
- returns the file if it exists

## Decision

Do not resolve #215 by simply taking the service-first wrapper yet.

Current decision: `needs-review` + `blocked:route-parity`.

## Required Fix Before Refresh/Merge

Before #215 can be refreshed and used as the root parent:

1. Restore `GET /download/{filename}` authorization behavior inside `messages_api_service.py` or a called service/helper.
2. Keep filename sanitization behavior equivalent or stricter.
3. Add targeted test proof for authorized vs unauthorized download access.
4. Then retry the #215 refresh/cherry-pick against current `main`.

## Current Safe Status

- #215 remains blocked.
- #58+ remains blocked.
- No merge, push, or retarget was performed during this review.
