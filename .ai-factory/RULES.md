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
- For non-trivial implementation work, use a short `step -> verify` loop, keep assumptions explicit, and prefer the smallest patch slice that satisfies the requested behavior over speculative abstractions or adjacent cleanup.
- For substantial clinic frontend UI/UX work, use `.ai-factory/skill-context/clinic-ui-ux-master/SKILL.md` as the AI Factory bridge and `.agents/skills/clinic-ui-ux-master/SKILL.md` as the canonical source of truth.
- Do not import runtime UI from `frontend/src/components/emr`; use `EMRContainerV2` and the v2 section primitives under `frontend/src/components/emr-v2/sections` instead. The legacy `SingleSheetEMR` and old EMR folder are retired.
- When sweeping React `prop-types`, treat runtime helpers and shared UI outside `emr-v2` as part of the same pass; do not leave obvious prop validation gaps behind when a file is already being touched.
- Shared singletons and providers must import `frontend/src/api/client.js` statically rather than through dynamic `import()` to avoid Vite chunking warnings and keep the API client singleton stable.
