# W2D online_queue_legacy_api_service cleanup

## What changed

Removed:

- `backend/app/services/online_queue_legacy_api_service.py`

## Why this was safe

The file was not a mounted endpoint owner and had no confirmed in-repo source
imports.

It duplicated legacy QR/online-queue compatibility behavior that no longer
belongs in the active runtime surface.

## What did not change

This slice did not change:

- QR queue runtime behavior
- route registration
- allocator logic
- OnlineDay lifecycle behavior

## Practical effect

This removes one more duplicate/unmounted legacy artifact without touching any
live queue path.
