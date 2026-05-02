# 2026-03-27 - Dynamic pricing payload normalization

## Context
- Admin `Dynamic Pricing` create rule flow failed with `422` even though the UI looked valid.
- Browser payload still sent uppercase enum values and empty-string optional fields.

## Root Cause
- The frontend form kept `rule_type` / `discount_type` in UI-friendly uppercase values.
- Optional fields such as `start_date`, `end_date`, `start_time`, `end_time`, `days_of_week`, `max_quantity`, `min_amount`, and `max_uses` were submitted as empty strings instead of `null`/omitted values.
- The backend schema is strict and expects lowercase enum values plus real datetime/number types for non-empty fields.

## Fix
- Normalize dynamic-pricing enum values to backend canonical lowercase before submit.
- Strip empty optional fields from the request payload.
- Render existing rule cards using enum normalization so backend-returned lowercase values display correctly.
- Clean up smoke data directly in Postgres after proof when the UI delete action is not reliable.

## Prevention
- When a form posts to a strict API schema, build a submission payload instead of passing raw UI state through unchanged.
- Avoid empty-string submissions for optional datetime and numeric fields.
- If a smoke leaves test data behind, remove it explicitly and record the cleanup path in the panel QA status log.
