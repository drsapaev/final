# Documentation Standards & Maintenance Rules

## 🎯 Goal
Ensure documentation remains **accurate**, **current**, and **useful** throughout the project lifecycle.

---

## 📜 Rule #1: Documentation is Code

Treat documentation with the same care as code.
- **Pull Requests (PRs)** must include documentation updates.
- **Refactoring code** means refactoring docs.
- **New features** require new or updated docs.

### Definition of Done (DoD)
A task is NOT done until:
1. [ ] Code is written and tested.
2. [ ] `README.md` (root or docs/) is updated if architecture changed.
3. [ ] `API_REFERENCE.md` is updated if endpoints changed.
4. [ ] `DEPLOYMENT_GUIDE.md` is updated if config/migrations changed.

---

## 🔄 Rule #2: Life Cycle Management

### 1. Creation
- Use clear filenames: `FEATURE_NAME_TYPE.md` (e.g., `QUEUE_SYSTEM_ARCHITECTURE.md`)
- Add to `docs/README.md` index immediately.

### 2. Maintenance
- **Update in place** for minor changes.
- **Versioning**: If a major rewrite is needed (v1 -> v2), rename the old one to `_v1` or move to archives if totally obsolete.

### 3. Archiving
- **NEVER DELETE** valuable history. Move to `docs/archives/`.
- Prefix: None needed if moving folder, but if renaming: `ARCHIVED_OriginalName.md`.
- Update indexes to remove links to archived files.

---

## 🤖 Rule #3: AI Agent Instructions

If you are an AI agent working on this project:

1. **Check for existing docs** before creating new ones.
2. **Read the LAWS** (`AUTHENTICATION_LAWS_FOR_AI.md`, `DOCTOR_AUTOCOMPLETE_LAWS_FOR_AI.md`) before touching sensitive areas.
3. **If you change code logic**, you **MUST** scan `docs/` for relevant files and update them.
   - Example: Changed `OnlineQueueEntry` model? Update `ONLINE_QUEUE_SYSTEM_GUIDE.md`.
4. **Do not create "Plan" artifacts in `docs/`**. Use the `brain/` directory or `implementation_plan.md` for ephemeral planning. Keep `docs/` for permanent reference.

---

## 🏗️ Folder Structure

```
c:\final\
├── docs/
│   ├── archives/          # Old/Obsolete files
│   ├── README.md          # Main Navigation
│   ├── API_REFERENCE.md   # Source of Truth for API
│   ├── DEPLOYMENT_GUIDE.md# Source of Truth for DevOps
│   └── ... (Topic specific guides)
└── README.md              # Entry point
```

---

## 📝 Writing Style Guide

- **Clear & Concise**: Use bullet points.
- **Code Blocks**: Always specify language (```python).
- **Links**: Use relative paths (`./file.md`).
- **Dates**: Add "Last Updated: YYYY-MM-DD" at the bottom of major guides.
- **SSOT**: Don't repeat identical info. Link to the source of truth.

---

*Version: 1.0*
*Last Updated: 2026-01-06*
