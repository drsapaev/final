# W2D next_ticket Semantic Options

## Option A: keep it as operational ticket-issuance action

### Meaning

Keep `next_ticket` conceptually alive as an operational action that issues the next department/day number and updates board-facing counters.

### Pros

- matches current runtime best
- smallest semantic drift from legacy behavior
- avoids pretending it is a queue-entry lifecycle action

### Risks

- preserves a legacy concept that does not fit SSOT cleanly
- keeps department/day counter semantics alive longer
- still needs a clear operational owner

### Compatibility impact

Low if kept as-is, medium if re-owned later.

### Rollout complexity

Low to medium.

## Option B: replace it with SSOT-backed ticket-issuance admin adapter

### Meaning

Preserve the business effect, but move ownership to an explicit operational admin adapter that sits outside the main queue allocator path.

### Pros

- cleaner than keeping raw OnlineDay logic forever
- aligns with target architecture better than pretending it is queue-domain
- gives the action a clearer operational owner

### Risks

- still requires a product decision that the action should survive
- requires department/day to SSOT-compatible mapping rules
- parity with legacy counters must be proven

### Compatibility impact

Medium.

### Rollout complexity

Medium to high.

## Option C: deprecate/retire because it no longer fits the target architecture

### Meaning

Treat `next_ticket` as a legacy-only operation that should disappear once usage is confirmed absent or replaced.

### Pros

- avoids rebuilding legacy semantics into the future system
- keeps target architecture cleaner
- matches the absence of confirmed in-repo consumers

### Risks

- route is still mounted
- manual or external usage may still exist
- retirement without usage proof is risky

### Compatibility impact

Potentially high if hidden consumers exist.

### Rollout complexity

Medium.

## Option D: rename/reframe later while preserving temporary compatibility

### Meaning

Keep the current route temporarily, but future-facing semantics would be reframed under a more honest name such as operational ticket issuance, while old naming survives only as compatibility.

### Pros

- makes semantics clearer
- reduces long-term confusion
- supports staged migration if survival is required

### Risks

- naming cleanup alone does not solve ownership
- still depends on whether the action should survive at all

### Compatibility impact

Medium.

### Rollout complexity

Medium.

## Comparison summary

Most realistic directions:

- Option C if the action is no longer needed
- Option B if the action still matters operationally

Least safe direction:

- treating it like a normal queue-domain operation
