# Next Execution Unit After Activation API Service Cleanup

Recommended next step:
- a dedicated review-first slice for
  `backend/app/services/clinic_management_api_service.py`

Why:
- `activation` is no longer the best mixed-risk candidate
- `clinic_management` remains the clearest non-protected survivor with
  behavior-bearing branch-scope drift
- protected auth/payment/queue/EMR candidates still require separate plan-gates
