# W1.9-T2 Payment B324 Security Review

Date: 2026-03-06  
Branch: `codex/w19-gate-blockers`  
Status: `pending human review`

## Scope

Protected payment zone review only:
- `app/services/payment_providers/click.py`
- `app/services/payment_webhook.py`

No payment logic or webhook behavior was modified.

## Evidence

Command executed:

```bash
cd backend
bandit -r app/services/payment_providers/click.py app/services/payment_webhook.py -f json
```

Findings:
- `B324` (weak MD5 hash) in:
  - `app/services/payment_providers/click.py:65`
  - `app/services/payment_providers/click.py:110`
  - `app/services/payment_providers/click.py:246`
  - `app/services/payment_webhook.py:60`

## Classification

| Location | Purpose | Classification | Reason |
|---|---|---|---|
| `click.py` (signature generation/verification) | Provider protocol signing | `3 requires architectural change` | Replacing MD5 in isolation can break Click protocol compatibility and requires provider-contract decision. |
| `payment_webhook.py` (Click signature verify) | Webhook signature validation | `3 requires architectural change` | Same protocol constraint; unilateral algorithm swap is unsafe. |

Secondary operational classification:
- `2 acceptable risk` only with explicit mitigation and risk acceptance while protocol remains MD5.

## Safe Mitigation (No Logic Change)

1. Keep strict replay window and signature timestamp validation in webhook path.
2. Keep source/IP allowlist and request-rate controls for payment webhook endpoints.
3. Keep full audit logs for signature mismatch and suspicious replay patterns.
4. Prepare provider-backed migration plan (dual-signature or provider-supported stronger algorithm), then implement with human approval.

## Decision

- Secure auto-fix is **not** possible in bounded autonomous mode.
- This remains **pending human review** because it is in a protected payment zone and tied to external protocol behavior.

