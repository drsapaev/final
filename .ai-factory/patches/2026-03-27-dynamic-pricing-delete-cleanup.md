# Dynamic pricing delete cleanup

## Root Cause
- `DELETE /api/v1/dynamic-pricing/pricing-rules/{rule_id}` failed on a pricing rule that already had linked `pricing_rule_services` rows.
- SQLAlchemy tried to synchronize those loaded child objects by setting `rule_id = NULL`, which violated the NOT NULL constraint on `pricing_rule_services.rule_id`.
- A linked `service_packages.pricing_rule_id` also needed to be detached so the parent rule could be removed cleanly.

## Fix
- Added ORM-aware cleanup for pricing rule dependencies before deletion:
  - delete linked `pricing_rule_services` rows
  - detach any `service_packages` that reference the rule by setting `pricing_rule_id = NULL`
- Switched the parent delete path to a bulk delete by `rule_id` instead of ORM `db.delete(rule)` to avoid session-side nullification of child rows.
- Added `cascade="all, delete-orphan"` on `PricingRule.rule_services` to align the model relationship with the delete lifecycle.

## Verification
- Targeted unit tests passed for the delete flow.
- Integration test covered a rule with both linked service rows and a package reference, and the delete returned `200`.
- Live API smoke on the running backend confirmed:
  - `DELETE /api/v1/dynamic-pricing/pricing-rules/3 -> 200`
  - the temporary package remained and its `pricing_rule_id` became `NULL`

## Evidence
- `output/playwright/dynamic-pricing-delete-smoke.log`

## Prevention
- For parent/child domain objects, prefer an explicit cleanup lifecycle or configured cascade before deleting the parent row.
- Avoid ORM parent deletes when the session may still synchronize loaded child rows into `NULL` updates on NOT NULL foreign keys.
