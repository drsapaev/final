# W2D next_ticket Replacement Options

## Option A: replace with SSOT queue-domain operation

### Idea

Map `next_ticket` to a modern SSOT queue-domain action.

### Advantages

- removes a legacy write path
- aligns everything under modern queue ownership
- reduces OnlineDay dependence

### Risks

- current semantics do not match SSOT queue-entry lifecycle
- no proven modern equivalent for “department/day naked counter issuance”
- high risk of changing numbering meaning and waiting-count behavior

### Migration complexity

High.

### Backward compatibility risk

High.

### Rollback complexity

Medium to high, because semantic drift could be subtle.

## Option B: replace with operational admin adapter over SSOT-compatible read/write surfaces

### Idea

Treat `next_ticket` as a legacy operational admin action and replace it later with a dedicated adapter, not a normal queue-domain entry flow.

### Advantages

- matches current operational nature better
- keeps replacement scope narrow
- allows board/stats parity to stay explicit

### Risks

- still requires product decision about whether the action should survive
- still needs department/day mapping rules
- may remain partially legacy-shaped even after replacement

### Migration complexity

Medium.

### Backward compatibility risk

Medium.

### Rollback complexity

Low to medium.

## Option C: keep legacy for now and defer

### Idea

Leave `next_ticket` on OnlineDay until product ownership is clarified.

### Advantages

- lowest immediate risk
- no parity drift
- keeps current mounted behavior intact

### Risks

- legacy island remains live longer
- documentation and operational ownership remain messy
- delays cleanup

### Migration complexity

Low now, higher later.

### Backward compatibility risk

Low.

### Rollback complexity

Very low.

## Option D: retire instead of replace

### Idea

If no real consumer remains, remove the route instead of rebuilding it.

### Advantages

- cleanest long-term outcome
- avoids rebuilding legacy semantics into new architecture

### Risks

- route is still mounted and may have manual/external users
- current repo audit cannot prove zero external dependency

### Migration complexity

Medium, because proof of non-use is required first.

### Backward compatibility risk

High unless non-use is proven.

### Rollback complexity

Low if guarded and staged, high if removed blindly.

## Current planning conclusion

The realistic near-term choices are:

- Option B if product confirms the action still matters
- Option C if ownership remains unclear
- Option D only after stronger usage evidence

Option A is not the safest first path because `next_ticket` does not behave like a normal SSOT queue operation today.
