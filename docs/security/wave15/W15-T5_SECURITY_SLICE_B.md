# W1.5-T5 Security Slice B (Bandit Findings)

Date: 2026-03-06  
Task: Backend security remediation (safe-only)  
Branch: `codex/w15-security-slice-b-bandit`  
Status: `pending human review`

## Must-Run Command

```bash
cd backend
bandit -r .
```

Execution notes:

- `bandit -r .` executed (initial text output hit Windows encoding noise; rerun with UTF-8/json output completed successfully).
- Full-scan artifact written:
  - `backend/bandit_full_wave15_post.json`
- App-scope comparison artifacts:
  - `backend/bandit_app_wave15.json` (pre-fix)
  - `backend/bandit_app_wave15_post.json` (post-fix)

## Findings Summary (app scope)

- Pre-fix:
  - total: `161`
  - high: `18`
  - medium: `16`
  - low: `127`
  - `B324`: `7`
  - `B701`: `11`
- Post-fix:
  - total: `158`
  - high: `15`
  - medium: `16`
  - low: `127`
  - `B324`: `4`
  - `B701`: `11`

## Safe Fixes Applied

1. `app/core/cache.py`
   - Updated non-cryptographic cache key hashing:
     - `hashlib.md5(...).hexdigest()` -> `hashlib.md5(..., usedforsecurity=False).hexdigest()`
   - Fixed two `B324` findings.

2. `app/services/ai/mock_provider.py`
   - Updated deterministic mock audio hash:
     - `hashlib.md5(audio_data[:100]).hexdigest()` -> `hashlib.md5(audio_data[:100], usedforsecurity=False).hexdigest()`
   - Fixed one `B324` finding.

## Remaining Issues Requiring Human Review

1. **Payment protected zone (`pending human review`)**
   - Remaining `B324` in:
     - `app/services/payment_providers/click.py` (3 locations)
     - `app/services/payment_webhook.py` (1 location)
   - Reason: payments are protected zone; signature/hash changes can affect external provider compatibility and cannot be auto-applied in bounded mode.

2. **`B701` (`jinja2 autoescape=False`) - potential rendering behavior change**
   - Remaining in print/pdf/ai/telegram template rendering paths.
   - Reason: blanket autoescape change can alter output semantics and needs explicit review/test plan.

## Diff Summary

- Files changed:
  - `backend/app/core/cache.py`
  - `backend/app/services/ai/mock_provider.py`
- `git diff --stat`:
  - `2 files changed, 9 insertions(+), 7 deletions(-)`

