## Assessment

### Confirmed in-repo usage

- `open_day`: No confirmed direct in-repo runtime consumer found
- `close_day`: No confirmed direct in-repo runtime consumer found
- related operational concept: Yes, but via `POST /api/v1/registrar/open-reception`, not via the legacy routes

### Implied operational usage

Yes.

The repo still contains strong workflow documentation and code comments describing a registrar action equivalent to "open reception now" / "close morning intake".

### Likely external/manual usage risk

**Medium**

Reasoning:

- the exact legacy routes are still mounted and admin-protected
- no current in-repo caller confirms they are dead
- no current in-repo caller confirms they are actively used either
- documentation and manuals still imply the workflow matters operationally
- current UI appears to use a newer route for a similar concept, which lowers but does not remove external/manual risk

### Confidence

**Medium**

The repo gives enough evidence to rule out "confirmed active in-repo caller", but not enough to safely rule out:

- external API clients
- manual Swagger / admin use
- operator habits based on older workflows

## What kind of change would be risky

The following changes remain risky without ops confirmation:

- changing `open_day` response semantics
- changing `close_day` response semantics
- fixing the current asymmetry between `Setting(category="queue")` and `OnlineDay.is_open`
- adding or removing broadcast behavior
- removing the routes outright

## What kind of change is not yet justified

A narrow runtime behavior fix is **not yet justified** purely from repo evidence, because the remaining uncertainty is now about operational usage, not code reachability.
