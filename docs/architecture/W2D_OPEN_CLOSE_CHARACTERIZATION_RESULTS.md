# W2D Open / Close Characterization Results

The current mounted runtime behavior is now characterization-tested in:

- [test_open_close_day_characterization.py](C:/final/backend/tests/characterization/test_open_close_day_characterization.py)

## Proven `open_day` Behavior

`open_day` currently:

- writes `queue::{dep}::{date}::open = 1`
- writes `queue::{dep}::{date}::start_number = requested_start_number`
- returns `start_number` from the request payload, not from canonical `OnlineDay`
- returns `is_open=True`
- calls legacy `_broadcast(...)`

When no `OnlineDay` exists yet:

- `load_stats(...)` creates one with default `start_number = 1`
- broadcasted stats therefore report `start_number = 1`
- response still reports the requested `start_number`

## Proven `close_day` Behavior

`close_day` currently:

- sets `OnlineDay.is_open = False`
- leaves `OnlineDay.start_number` unchanged
- returns `load_stats(...)`
- does **not** call `_broadcast(...)`

## Proven Drift

### 1. Split state sources

`open_day` and `close_day` do not write the same canonical source.

- `open_day` writes `Setting(category="queue")`
- `close_day` writes `OnlineDay`

### 2. Response-vs-state mismatch in `open_day`

`open_day` can return:

- `start_number = requested value`

while the actual `OnlineDay.start_number` remains:

- `1` (default created by `load_stats(...)`)

### 3. Broadcast mismatch

- `open_day` broadcasts
- `close_day` does not

### 4. Open-then-close inconsistency

In the tested current truth:

- after `open_day(start_number=42)`, setting storage says `start_number=42`
- after `close_day`, `OnlineDay.is_open=False`
- but the legacy `queue::{dep}::{date}::open` setting still remains `"1"`
- and `OnlineDay.start_number` can still be `1`

## Consistency Finding

The pair is not internally consistent today. The drift is real and code-backed, not just a documentation mismatch.
