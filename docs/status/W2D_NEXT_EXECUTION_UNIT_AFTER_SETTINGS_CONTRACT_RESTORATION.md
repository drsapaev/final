# Next Execution Unit After Settings Contract Restoration

Recommended next step:
- a dedicated non-protected mixed-risk review for
  `backend/app/services/activation_api_service.py`
  or `backend/app/services/clinic_management_api_service.py`

Why:
- the `settings` contract-drift tail is resolved
- the remaining non-protected residue pool is now down to behavior-bearing
  candidates, not blind cleanup survivors
- protected-domain candidates still require separate plan-gates
