# Project Rules

> Short, actionable rules and conventions for this project. Loaded automatically by $2.

## Rules

- Always select and explicitly use the relevant AI Factory skill set before implementing a plan, and keep the active plan visible until all planned steps are completed or blocked.
- When an OpenHands-style workflow or compatible agent environment is available, keep implementation progress, completed steps, blockers, and next actions recorded in a resume-friendly format instead of relying on memory.
- For auth or smoke work, resolve working credentials from the live database or live auth response first; do not guess usernames from docs, stale artifacts, or profile token files.
- Never surface raw browser network failures like `Failed to fetch` to users when a clear, localized recovery message can be shown instead.
- Never hardcode backend origins or legacy ports in frontend fetch calls; use the shared runtime URL helper (`buildApiUrl` / `buildWsUrl`) so browser smoke stays aligned with the canonical backend port (`18000` in the local stack).
- Active backend scripts and docs must use port `18000`; reserve `8000` only for archived evidence or price data, never for runnable instructions, startup snippets, or smoke guidance.
- User-facing network failures should use the shared localized pattern `Не удалось ... Проверьте соединение и попробуйте снова.` unless the screen explicitly needs a more specific server response.
