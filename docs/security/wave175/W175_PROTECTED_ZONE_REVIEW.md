# W1.75 Protected Zone Findings Classification

Date: 2026-03-06  
Branch: `codex/w175-gate-readiness`  
Status: `done`

Classification scale:
1. `safe to auto-fix`
2. `requires human review`
3. `acceptable risk with mitigation`
4. `false positive`

## Classified Findings

| Area | Finding | Evidence | Class | Reason | Recommended action |
|---|---|---|---|---|---|
| payment services (protected) | MD5 signature usage (`B324`) in Click/webhook | `app/services/payment_providers/click.py`, `app/services/payment_webhook.py` | 2 | Payment signature compatibility is provider/protocol-coupled and protected-zone sensitive | Human-reviewed change plan with provider test vectors |
| template rendering (partly protected via EMR/print outputs) | `B701` in print template stacks | `app/api/v1/endpoints/print_templates.py`, `app/services/print_templates_api_service.py`, `app/services/pdf_service.py` | 2 | `autoescape` changes can alter rendered medical documents and business output semantics | Human-reviewed staged hardening with snapshot tests |
| PDF generation | Frontend `jspdf` critical dependency risk | `frontend/src/components/laboratory/LabReportGenerator.jsx`, `npm audit` critical on `jspdf` | 3 | Critical advisory exists, but current usage is constrained to text/table generation; no direct `addJS` flow observed in this component | Temporary mitigations + dedicated major-upgrade slice |
| encryption usage (non-protected control slice) | Non-cryptographic MD5 in cache/mock contexts | `app/core/cache.py`, `app/services/ai/mock_provider.py` | 1 | Not used for security decisions; safe `usedforsecurity=False` remediation already applied in Wave 1.5 | Keep as-is, no blocker |
| template rendering (non-browser sinks) | `B701` in AI prompt/Telegram template string building | `app/services/ai_service.py`, `app/services/telegram_service.py` | 4 | Bandit XSS-oriented heuristic triggers on generic Jinja environment; these paths build LLM prompts/messages, not HTML DOM output | Keep tracked; treat as non-blocking false positive for XSS class |

## Protected-Zone Summary

- Open protected-zone risks requiring human review:
  - Payment signature/hash handling (`B324`) in Click + payment webhook.
  - Print/PDF template `autoescape` hardening (`B701`) where output compatibility matters.
- These items remain **pending human review** and should not be auto-executed in bounded mode.
