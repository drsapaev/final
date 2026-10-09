# Preserve doctor publication and dirty website fields across concurrent updates

**Severity:** Medium

**Tags:** public-site, doctor-profile, publication-lock, admin-form, dirty-fields

## Problem

Clearing an account's display name only selected an already-published doctor card for locking. A concurrent publisher can hold a still-hidden card while validating the old name, so the account update could miss that row. Separately, the service editor treated a same-service refresh as a reason to skip every field update; a dirty description could keep a stale service name and overwrite a catalog rename on the next website save.

## Resolution

When the account display name is cleared, lock all linked doctor rows in stable ID order, refresh their state after acquiring the lock, and hide any card that is published at that point. In the website editor, merge refreshed server values with only the individually edited fields. Add regression coverage for the catalog rename and preserve the existing lifecycle scenarios.

## Prevention

Every write that changes publication eligibility must lock the same doctor rows before checking current publication state. Refresh ORM state after waiting on row locks. In forms backed by independently editable records, track dirty fields rather than treating the whole record as dirty; verify that a server refresh cannot cause a stale canonical value to be submitted.
