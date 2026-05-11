[← Previous Page](PANEL_QA_CHECKLIST.md) · [Back to README](../README.md)

# ADM-06 Browser Smoke Checklist

Compact manual QA checklist extracted from the live service-catalog browser smoke.
Use it when you only need to verify the service-prefix guardrail without running
the full panel runbook.

Status: verified in live admin smoke on 2026-03-29.
Evidence artifacts are generated locally under ignored `output/playwright/` when the smoke is rerun; they are not required as committed files.

## Preconditions

- Admin user is logged in.
- A live admin stack is available.
- Open the service catalog at `/admin?servicesTab=catalog&section=services`.

## Checklist

- [x] Open `Услуги` -> `Справочник услуг`.
- [x] Click `Добавить услугу`.
- [x] Negative case: select `Лабораторные анализы`, enter code `P77`, price `10000`, duration `15`.
  - Verified: inline warning `Код P77 не подходит для группы "Лаборатория"` blocks submit before persistence.
  - Verified: no `POST /services` request is sent for the invalid lab code.
- [x] Positive case: change category to `Прочие услуги`, code to `O77`, price `12000`, duration `20`.
  - Verified: warning disappears.
  - Verified: `Сохранить` succeeds.
  - Verified: table row `QA Mismatch Smoke` appears with canonical code `O77`.
  - Verified: `POST /services -> 200`.
- [x] Refresh the table once and confirm the new row persists.
- [x] Capture screenshot and network evidence for both cases.

## Pass Criteria

- Mismatched lab code is blocked before persistence.
- Valid other-service code saves successfully.
- The service table shows the canonical code and updated count after save.

## Verification Notes

- Primary source of truth: admin services UI.
- Secondary source of truth: registrar services API / service creation network response.
- This checklist is closed in the current runbook cycle; see [`P2 ADM-06-BROWSER-SMOKE`](../.ai-factory/logs/PANEL_QA_IMPLEMENTATION_STATUS.md) for the tracked live proof.

## Common Failures

- Warning is missing but the code is still invalid.
- Submit goes through despite the warning.
- Valid save succeeds but the table does not refresh.

## See Also

- [PANEL_QA_CHECKLIST.md](PANEL_QA_CHECKLIST.md) - full SSOT runbook for all panels
- [CHANGELOG.md](../CHANGELOG.md) - cycle summary and release notes
- [AI_MCP_QA_CHECKLIST.md](AI_MCP_QA_CHECKLIST.md) - other QA checklist in this docs set
