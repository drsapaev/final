# Patch: activation smoke persistence and table guard

**Date:** 2026-03-27

## Context

The activation admin panel loaded successfully after the API/client migration, but the create-key flow initially appeared empty because `issue_key()` only flushed rows and did not commit, and the table renderer crashed when a row came back as an undefined payload during refetch.

## Changes

- Committed activation key issuance in `backend/app/core/activation.py`
- Switched the activation panel to the shared API client and activation endpoints in `frontend/src/components/admin/ActivationSystem.jsx`
- Hardened `ActivationSystem` row renderers against undefined activation rows after refetch
- Kept the MacOS table empty-state wrapper valid for table rows

## Verification

- Live browser smoke on `http://127.0.0.1:5174/admin/settings?section=activation` created two trial keys and revoked both successfully
- Backend API confirmed `activation/list` reflected the keys and `activation/status` remained `NO_ACTIVATION`
- `npx eslint src/components/admin/ActivationSystem.jsx` passed
- `npm run build` passed

## Notes

The activation panel now behaves like the rest of the admin runbook: create, refetch, revoke, and cleanup can be executed without a browser crash or a lost write.
