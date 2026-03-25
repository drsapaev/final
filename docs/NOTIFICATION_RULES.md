# Notification rules for panel workflows

- Use `frontend/src/services/notify.js` as the single notification API in panel workflows.
- Do not use `alert(...)` in panel workflows.
- Do not import toast libraries (for example `react-toastify`) directly in panel files.
- Use helper methods by intent:
  - `notify.success(...)`
  - `notify.error(...)`
  - `notify.info(...)`
  - `notify.warning(...)`
