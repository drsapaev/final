<#
Retired legacy login diagnostic helper.

This script previously mixed local database-file checks with a hard-coded
login probe. That path no longer represents the PostgreSQL runtime or the
current authentication contract.
#>

Write-Error @"
backend/Check-LoginDiagnostics.ps1 is retired.

Use the canonical backend tests, configured PostgreSQL environment, and current
auth smoke helpers instead of this legacy local login diagnostic.

Suggested checks:
  cd backend
  python -m pytest tests/unit
  python -m pytest tests/integration/test_rbac_matrix.py
"@

exit 2
