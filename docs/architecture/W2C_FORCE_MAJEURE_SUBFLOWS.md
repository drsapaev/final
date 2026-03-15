# Wave 2C Force Majeure Runtime Subflows

Date: 2026-03-09
Mode: characterization-first

## FM-SF-01 Mounted Transfer To Tomorrow

- Entry point: `/api/v1/force-majeure/transfer`
- Starting state: current-day rows in `waiting` or `called`
- Action: bulk transfer selected or all pending rows to tomorrow's queue for the
  same specialist
- Queue effect: creates a new tomorrow row and cancels the original row
- Numbering effect: new row gets `MAX(number)+1` in tomorrow queue, excluding
  only `cancelled`
- Queue-time effect: new row gets fresh `datetime.utcnow()`, not the original
  `queue_time`
- Fairness effect: explicit override via `priority=2`; transferred rows become
  high-priority rows for tomorrow
- Final state: original row `cancelled`, new row `waiting`,
  `source="force_majeure_transfer"`

## FM-SF-02 Mounted Cancel With Refund

- Entry point: `/api/v1/force-majeure/cancel-with-refund`
- Starting state: current-day rows in `waiting` or `called`
- Action: cancel rows and create deposit credit or refund request for paid
  visits
- Queue effect: no new queue row
- Numbering effect: none
- Queue-time effect: active queue lifecycle ends; original row is cancelled
- Fairness effect: row is removed from active queue
- Final state: original row `cancelled`, payment side-effects recorded in
  deposit or refund models

## FM-SF-03 Pending Entry Selection

- Entry point: `/api/v1/force-majeure/pending-entries`
- Starting state: specialist-day queue
- Action: fetch eligible rows for transfer/cancel operation
- Queue effect: none
- Numbering effect: none
- Queue-time effect: none
- Fairness effect: none
- Final state: read-only payload with current pending rows

## Characterized Runtime Facts

- Transfer does not reuse or mutate the original row in place; it creates a new
  row for tomorrow.
- Transfer does not apply a canonical duplicate gate on the tomorrow queue.
- If the patient already has an active tomorrow row, transfer still creates one
  more `force_majeure_transfer` row.
- Transfer preserves visit linkage by copying `visit_id`.
