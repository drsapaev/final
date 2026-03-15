# Next Execution Unit After System Management API Service Cleanup

Recommended next step:
- another review-first dead endpoint or router-duplicate slice

Why:
- the remaining residue pool is smaller and increasingly mixed between
  blocked endpoint gaps and service-side router duplicates
- `settings.py` is still not a clean deletion candidate while frontend
  references remain live
- each next candidate still needs explicit mounted-owner and live-usage proof
  before any deletion
