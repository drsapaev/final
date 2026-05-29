# Telegram Bot + Mini App Release Gate Evidence

## Release

- Date: 2026-05-27
- Scope: Telegram onboarding policy, duplicate-safe registrar review, TelegramManager operational inbox, Mini App onboarding shell, safe analytics/export, release-gate automation
- Status: certified `100/100` for the current release scope

## Canonical Statement

Unknown patients can request booking, but cannot become Patients or confirmed Visits until Registrar/Admin review.

## Final Scorecard

- Telegram informativity: `5/5`
- Mini App informativity: `5/5`
- Telegram usability: `5/5`
- Mini App usability: `5/5`
- Patient utility: `5/5`
- Staff utility: `5/5`
- Business utility: `5/5`
- Final score: `100/100`

## Privacy Gate

Status: `Pass`

Confirmed protections in this release slice:

- no auto-created Patient for unknown Telegram or Mini App users
- no auto-created confirmed Appointment or Visit
- onboarding scope blocked from visits, queue, payments, documents, results, and EMR-linked data
- duplicate search returns masked candidate data only
- audit payloads redact patient references and safe-note content
- CSV export masks contact name and phone
- telemetry whitelist blocks raw token, medical, EMR, and payment leakage
- browser QA artifacts contain no raw `pma_` or `pmo_` tokens, raw API text, payment ids, or medical text

## Release Findings

- P0: `0`
- P1: `0`
- P2: `0`

## Validation Commands Run

### Backend onboarding and privacy

```powershell
C:\final\scripts\run_backend_pytest.ps1 tests/unit/test_patient_onboarding_request_policy.py tests/unit/test_telemetry_onboarding_privacy.py
```

Result: `27 passed`

### Backend OpenAPI contract

```powershell
C:\final\scripts\run_backend_pytest.ps1 tests/test_openapi_contract.py
```

Result: `24 passed`

### Frontend Telegram + Mini App tests

```powershell
cd C:\final\frontend
npm run test:run -- telegramManagerOnboardingRequests telegramMiniApp
```

Result: `25 passed`

### Browser QA smoke

```powershell
cd C:\final\frontend
npx playwright test e2e/telegram-miniapp-release-gate.spec.js --project=chromium --workers=1 --reporter=line
```

Result: `42 passed`

### Frontend production build

```powershell
cd C:\final\frontend
npm run build
```

Result: `passed`

### Diff hygiene

```powershell
git diff --check
```

Result: `passed`

### Automated release gate

```powershell
C:\final\scripts\telegram_miniapp_release_gate_score.ps1
```

Result: `100/100`, `Privacy Gate: Pass`, `P0: 0`, `P1: 0`, `P2: 0`

## Evidence Paths

- Release gate rule: [telegram_mini_app_operational_ux.md](/C:/final/docs/release_gates/telegram_mini_app_operational_ux.md)
- Release gate JSON report: [telegram_mini_app_release_gate_score.json](/C:/final/docs/release_gates/telegram_mini_app_release_gate_score.json)
- Browser QA artifact folder: [telegram-miniapp-release-gate](/C:/final/output/playwright/telegram-miniapp-release-gate)
- Mini App onboarding 375: [miniapp-onboarding-new-375.png](/C:/final/output/playwright/telegram-miniapp-release-gate/miniapp-onboarding-new-375.png)
- Mini App linked cabinet 1920: [miniapp-linked-cabinet-1920.png](/C:/final/output/playwright/telegram-miniapp-release-gate/miniapp-linked-cabinet-1920.png)
- Mini App expired token 768: [miniapp-expired-token-768.png](/C:/final/output/playwright/telegram-miniapp-release-gate/miniapp-expired-token-768.png)
- TelegramManager dashboard: [telegram-manager-dashboard-1280.png](/C:/final/output/playwright/telegram-miniapp-release-gate/telegram-manager-dashboard-1280.png)
- TelegramManager duplicate review modal: [telegram-manager-link-modal-1280.png](/C:/final/output/playwright/telegram-miniapp-release-gate/telegram-manager-link-modal-1280.png)
- Backend policy tests: [test_patient_onboarding_request_policy.py](/C:/final/backend/tests/unit/test_patient_onboarding_request_policy.py)
- Telemetry privacy tests: [test_telemetry_onboarding_privacy.py](/C:/final/backend/tests/unit/test_telemetry_onboarding_privacy.py)
- Browser smoke spec: [telegram-miniapp-release-gate.spec.js](/C:/final/frontend/e2e/telegram-miniapp-release-gate.spec.js)
- Release-gate script: [telegram_miniapp_release_gate_score.ps1](/C:/final/scripts/telegram_miniapp_release_gate_score.ps1)

## API Evidence

Validated onboarding and staff-review routes:

- `POST /api/v1/telegram/mini-app/onboarding/requests`
- `POST /api/v1/telegram/mini-app/onboarding/status`
- `GET /api/v1/telegram/onboarding/requests`
- `GET /api/v1/telegram/onboarding/analytics/summary`
- `GET /api/v1/telegram/onboarding/requests/export`
- `POST /api/v1/telegram/onboarding/requests/{request_id}/search-patients`
- `POST /api/v1/telegram/onboarding/requests/{request_id}/link-existing`
- `POST /api/v1/telegram/onboarding/requests/{request_id}/create-patient`
- `POST /api/v1/telegram/onboarding/requests/{request_id}/request-more-info`
- `POST /api/v1/telegram/onboarding/requests/{request_id}/reject`

## DB Migration Evidence

- Active onboarding revision: `0029_tg_patient_onboarding`
- Alembic chain check: `heads` and `history` passed
- Existing migrations were preserved; no historical revision was edited

## Browser QA Matrix

Validated viewports:

- `375`
- `768`
- `1280`
- `1920`

Validated states:

- linked cabinet
- onboarding new
- onboarding pending
- needs more info
- rejected
- linked existing
- created patient
- expired token
- missing token
- wrong-section token
- registrar inbox
- duplicate review modal

Assertions that passed across the checked evidence:

- no horizontal overflow
- no clipped CTA
- no raw token text
- no raw API text
- no payment leakage
- no medical leakage
- no unhandled page errors in the checked smoke

## Telemetry Events

Whitelisted onboarding events validated:

- `patient_onboarding_started`
- `patient_onboarding_opened`
- `patient_onboarding_submitted`
- `patient_onboarding_pending_review`
- `patient_onboarding_needs_more_info`
- `registrar_onboarding_reviewed`
- `patient_onboarding_linked_existing`
- `patient_onboarding_created_patient`
- `patient_onboarding_rejected`
- `patient_onboarding_expired`

## Known Limitations

- No release-blocking limitations remain in the certified onboarding scope.
- Disposable DB upgrade remains conditional on `DATABASE_URL_TEST`; it was not available in this local workspace during this evidence run.
- CI now wires `DATABASE_URL_TEST` through the `telegram-miniapp-release-gate` job in [ci-cd-unified.yml](/C:/final/.github/workflows/ci-cd-unified.yml), so the disposable Postgres Alembic proof can run remotely even when a local disposable DB is unavailable.
