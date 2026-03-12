## Decision

`A) continue the same QR pilot after this fix`

## Why this is the safest next step

- the QR direct-SQL characterization family is now green in both SQLite and
  Postgres lanes
- the latest blocker was resolved narrowly as expectation drift
- no broader datetime redesign was required
- the dual-lane pilot strategy remains the most reliable way to keep finding
  real DB-lane drift without broad fixture churn

## Why broader moves are not chosen yet

- there is no evidence here that a wider datetime or fixture-layer rewrite is
  justified
- there is no newly discovered QR-family blocker that requires another
  immediate drift-fix slice
- the cleanest next move is to continue bounded pilot expansion with the same
  repeatable method

## Practical next slice

Continue the validated Postgres pilot with the next bounded family:

- [test_confirmation_split_flow_characterization.py](C:/final/backend/tests/characterization/test_confirmation_split_flow_characterization.py)

That keeps the pilot expanding through nearby queue-sensitive characterization
coverage without widening scope.
