# Protect public-site publication writes

**Severity:** Medium

**Tags:** public-site, publication, admin, async-state, batch-update

## Problem

The generic service batch writer accepted website-owned fields through `setattr`, bypassing the publication endpoint's slug, completeness, and first-publication timestamp rules. The doctor editor also allowed a pending save response from one doctor to update the form after the same modal had switched to another doctor.

## Root cause

The batch endpoint shared an operational update path with website publication state, while the frontend save handler had no request-context check. The GET request was guarded on cleanup, but the PUT response, error, and finalizer were not.

## Resolution

Reject website-owned publication fields before the batch writer locks or mutates rows, and normalize/reject blank shared service names consistently with the single-update path. Associate doctor website requests with a generation that changes when the selected doctor or modal context changes; ignore stale save outcomes and reset the pending state for the new context.

## Prevention

Keep publication lifecycle fields behind their dedicated service operation. Add regression coverage for batch publication bypasses and for switching the selected doctor while a save is pending, including numeric API IDs paired with string UI IDs.
