# W2D Appointments QRCode Retirement Options

Date: 2026-03-11
Mode: docs-only review

## Option 1: Keep as-is for now

### Pros

- zero change risk
- no consumer assumptions required

### Cons

- preserves another mounted legacy surface
- keeps the OnlineDay-adjacent API surface larger than necessary
- hides that this route is only a stub/compatibility helper

### Assessment

Safe, but low architectural value.

## Option 2: Deprecation-prep without removal

### Pros

- smallest honest next step
- keeps runtime behavior unchanged
- makes the route's compatibility-only status explicit
- reduces future retirement ambiguity

### Cons

- route still remains mounted
- does not immediately shrink runtime surface

### Assessment

Best bounded next step if the route has no confirmed live consumer.

## Option 3: Immediate retirement/removal

### Pros

- maximum cleanup value

### Cons

- riskier without external/manual usage confirmation
- harder rollback if some untracked consumer still exists

### Assessment

Too aggressive for the current evidence level.

## Preferred option

`Deprecation-prep without removal`

This route is a good candidate for the same treatment already applied to other
legacy compatibility surfaces:

- keep mounted
- preserve behavior
- mark and document it as deprecated / compatibility-only

That gives architectural progress without pretending we have stronger consumer
evidence than we do.
