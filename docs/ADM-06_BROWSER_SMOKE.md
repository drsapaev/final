[← Previous Page](PANEL_QA_CHECKLIST.md) · [Back to README](../README.md)

# ADM-06 Browser Smoke Checklist

Compact manual QA checklist extracted from the live service-catalog browser smoke.
Use it when you only need to verify the service-prefix guardrail without running
the full panel runbook.

## Preconditions

- Admin user is logged in.
- A live admin stack is available.
- Open the service catalog at `/admin?servicesTab=catalog&section=services`.

## Checklist

- [ ] Open `Услуги` -> `Справочник услуг`.
- [ ] Click `Добавить услугу`.
- [ ] Negative case: select `Лабораторные анализы`, enter code `P77`, price `10000`, duration `15`.
  - Expect inline warning: `Код P77 не подходит для группы "Лаборатория"`.
  - Expect `Сохранить` to stay blocked.
  - Expect no `POST /services` request.
- [ ] Positive case: change category to `Прочие услуги`, code to `O77`, price `12000`, duration `20`.
  - Expect the warning to disappear.
  - Expect `Сохранить` to succeed.
  - Expect a new table row `QA Mismatch Smoke` with canonical code `O77`.
  - Expect `POST /services -> 200`.
- [ ] Refresh the table once and confirm the new row persists.
- [ ] Capture screenshot and network evidence for both cases.

## Pass Criteria

- Mismatched lab code is blocked before persistence.
- Valid other-service code saves successfully.
- The service table shows the canonical code and updated count after save.

## Common Failures

- Warning is missing but the code is still invalid.
- Submit goes through despite the warning.
- Valid save succeeds but the table does not refresh.

## See Also

- [PANEL_QA_CHECKLIST.md](PANEL_QA_CHECKLIST.md) - full SSOT runbook for all panels
- [CHANGELOG.md](../CHANGELOG.md) - cycle summary and release notes
- [AI_MCP_QA_CHECKLIST.md](AI_MCP_QA_CHECKLIST.md) - other QA checklist in this docs set
