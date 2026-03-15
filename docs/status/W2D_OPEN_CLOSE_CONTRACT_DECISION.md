# W2D Open / Close Contract Decision

## Verdict

`KEEP_AND_REFRAME`

## Meaning Of This Verdict

`open_day` and `close_day` should remain mounted for now, but they should be understood as:

- legacy operational admin lifecycle actions
- not queue-domain operations
- not part of the main SSOT allocator architecture

## Why This Verdict Fits Best

- there is no clean SSOT equivalent today
- real external/manual usage is still unresolved
- the routes still mutate visible legacy department/day state
- immediate deprecation would be riskier than first characterizing the live legacy behavior

## Explicit Position Per Route

### `open_day`

- survive for now: yes
- target framing: operational admin lifecycle action
- long-term possibility: deprecate later if no real usage remains

### `close_day`

- survive for now: yes
- target framing: operational admin lifecycle action
- long-term possibility: deprecate later if no real usage remains

## Rejected Alternatives

- `REPLACE_WITH_ADMIN_ADAPTER`
  - rejected for now because the routes do not yet have characterized parity and do not map cleanly to SSOT semantics
- `DEPRECATE_LATER`
  - too early as the primary decision for both routes together; the pair still needs runtime characterization first
- `RETIRE_CANDIDATE`
  - too strong before external/manual usage is clarified
- `HUMAN_REVIEW_NEEDED`
  - not chosen because there is still a safe deterministic next engineering step: characterize the paired runtime behavior
