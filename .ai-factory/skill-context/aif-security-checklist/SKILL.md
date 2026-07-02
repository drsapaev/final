# `aif-security-checklist` Context

Read `../common/SKILL.md` first.

## Project-Specific Notes

- Treat RBAC, EMR auditability, billing correctness, and fail-closed auth as high-priority checks.
- Watch for stale CORS/origin settings, unsafe direct ORM usage, and normalization bugs that can bypass validation.
- For this repo, security reviews should pay special attention to role-based routes, queue actions, payment webhooks, and settings endpoints.
- If a security finding depends on runtime ports or hosts, verify against the current `18000` / `5173` / `55432` contour.

