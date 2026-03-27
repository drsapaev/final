# 2026-03-27 - Discount benefits payload normalization

## Context
- Admin `Discount Benefits` create discount flow failed with `422` despite a valid-looking form.
- The frontend was submitting optional fields as empty strings, which the backend schema rejects.

## Root Cause
- `discountForm`, `benefitForm`, and `loyaltyForm` were sent directly to the API without cleaning optional inputs.
- `start_date`, `end_date`, `max_discount`, `usage_limit`, and similar fields were present as `""` instead of being omitted.

## Fix
- Added a small payload sanitizer that strips empty strings, `null`, `undefined`, empty arrays, and `NaN`-like numbers before submit.
- Applied the sanitizer to discount, benefit, and loyalty create flows.
- Verified the full flow by creating a test discount and then deleting the smoke row directly from Postgres to keep the panel clean.

## Prevention
- Any admin form that posts to a strict schema should normalize optional values before submit.
- For smoke flows, always clean up the test row and record the cleanup path in the panel QA status log.
