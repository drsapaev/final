# Wave 2C Next Execution Unit After QR Characterization

Date: 2026-03-09
Status: `SAFE_NEXT_STEP_IDENTIFIED`

## Recommended Next Step

`narrow seam extraction`

## Exact Target

Extract the QR-specific create-branch handoff(s) from mounted
`qr_queue.py::full_update_online_entry()` so that:

- raw SQL numbering is no longer hidden inline in the monolithic endpoint
- first-fill and edit-existing additional-service branches get an explicit QR-local seam
- no numbering, source, queue_time, or fairness semantics change

## Why This Is The Best Next Step

- runtime behavior is now characterized well enough
- the remaining blocker is coupling, not lack of evidence
- direct migration to `QueueDomainService.allocate_ticket()` would still be too
  broad from the current monolithic endpoint

## Not Recommended Yet

- broad QR migration
- QR allocator redesign
- OnlineDay / force-majeure work
- contract rewrite before extraction
