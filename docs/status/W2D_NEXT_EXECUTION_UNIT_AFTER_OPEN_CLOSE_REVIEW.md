# W2D Next Execution Unit After Open / Close Review

## Recommended Next Step

`open_day / close_day characterization pass`

## Why This Is Safest

This is the highest-signal next slice because:

- the routes remain live and mounted
- their current runtime behavior is asymmetric
- no replacement should be designed before that behavior is locked down

Characterization should cover:

- `open_day` state mutation behavior
- `close_day` state mutation behavior
- response parity
- broadcast side effects
- consumer/usage assumptions where they can be evidenced

## Why Broader Replacement Is Not Chosen Yet

- there is still no clean SSOT equivalent
- external/manual usage remains unresolved
- the current pair is not even internally symmetric enough to replace safely without first documenting real behavior
