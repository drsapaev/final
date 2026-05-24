# Demo Users

All demo users use the shared password:

```text
demo12345
```

| Role | Username / Email | Main UI Area |
| --- | --- | --- |
| Admin | `admin@example.com` | Admin setup and management |
| Registrar | `registrar@example.com` | Registrar panel, patients, queue, visits |
| Doctor | `doctor@example.com` | General doctor workflow |
| Cashier | `cashier@example.com` | Payments and receipts |
| Lab | `lab@example.com` | Lab reporting |
| Doctor | `cardio@example.com` | Cardiology doctor route |
| Doctor | `derma@example.com` | Dermatology doctor route |
| Doctor | `dentist@example.com` | Dentistry doctor route |

These identities are created by:

```powershell
cd C:\final\backend
$env:ENV="dev"
$env:DATABASE_URL="postgresql+psycopg://clinic:clinicpwd@localhost:5432/clinic_dev"
python -m app.scripts.dev_seed --profile demo --confirm-dev-seed
```

The seed also creates departments, services, doctors, schedules, patients,
today's queue entries, visits, payments, EMR examples, lab reports, and a small
audit marker for manual UI testing.

For local Admin/Cashier login smoke, set the existing development-only 2FA
override if your local auth config enforces critical-role 2FA:

```powershell
$env:DISABLE_2FA_REQUIREMENT="1"
```
