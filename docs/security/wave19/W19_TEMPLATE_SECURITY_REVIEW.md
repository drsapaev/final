# W1.9-T3 Template Rendering Security Review (B701)

Date: 2026-03-06  
Branch: `codex/w19-gate-blockers`  
Status: `done`

## Scope

Reviewed paths:
- print templates endpoints/services
- PDF generation service
- AI and Telegram template rendering paths

No template behavior or production rendering logic was changed.

## Evidence

Command executed:

```bash
cd backend
bandit -r app/api/v1/endpoints/print_templates.py app/services/print_templates_api_service.py app/services/pdf_service.py app/services/ai_service.py app/services/telegram_service.py -f json
```

Current targeted result:
- `B701` findings in all reviewed groups.
- Total targeted findings: `15 high` (including payment files in broader targeted run).

## Classification

| Area | Files | Classification | Rationale |
|---|---|---|---|
| Print template validation/preview | `app/api/v1/endpoints/print_templates.py`, `app/services/print_templates_api_service.py` | `requires autoescape change` | Uses `Environment()` with user/template content rendering. Hardening can change output semantics and needs controlled rollout. |
| PDF template rendering | `app/services/pdf_service.py` | `acceptable risk` | Server-side PDF output path; risk is lower than browser HTML sinks, but still needs explicit render-policy hardening plan. |
| AI prompt rendering | `app/services/ai_service.py` | `false positive` (for XSS class) | Template output is prompt text, not browser DOM output. |
| Telegram message template rendering | `app/services/telegram_service.py` | `false positive` (for XSS class) | Output target is Telegram message API, not browser DOM. |

## Follow-up Guidance

1. Build a staged hardening slice for print/PDF paths:
- map templates requiring raw HTML behavior;
- introduce `select_autoescape`/explicit escaping policy with snapshot regression tests.
2. Keep AI/Telegram B701 entries tracked as non-browser false positives unless sink changes.
3. Any print/PDF behavioral change in protected/document-critical flows should be human-reviewed before merge.

