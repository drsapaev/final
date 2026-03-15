# W2D online_queue_new_api_service cleanup plan

Date: 2026-03-11
Mode: bounded cleanup

## In scope

- `backend/app/services/online_queue_new_api_service.py`
- cleanup docs/status

## Why this file is a candidate

The file contains router-like `/online-queue/*` behavior under `services/`, but
current repo evidence shows:

- no confirmed in-repo source import of `online_queue_new_api_service`
- no route registration through this file
- no direct backend test dependency

It matches the already-documented pattern of unmounted duplicate queue modules.

## Why this is the narrowest safe cleanup

This is duplicate/unmounted residue removal only.

The slice intentionally does not:

- change mounted `online_queue_new.py`
- change QR or queue domain behavior
- change queue allocation semantics

## Validation plan

- OpenAPI contract check
- full backend suite
