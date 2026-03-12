# W2D Next Execution Unit After queue_batch_service Cleanup

Date: 2026-03-11
Mode: status decision

## Recommended next step

`duplicate/unmounted residue review`

## Why this is the safest next step

`queue_batch_service.py` was removable only after explicit evidence showed that
the mounted runtime already lives elsewhere.

The safest pattern remains:

- review one residue candidate
- remove it only when imports/runtime ownership are clean
- revalidate OpenAPI and the backend suite

## Why broader action is not chosen yet

- blocked operational tails remain blocked
- board semantics remain product-blocked
- `queue_batch_repository.py` is still exercised by characterization tests, so
  it is not the next blind cleanup target
