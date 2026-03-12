# W2D appointments.stats retirement options

## Option A — Keep as duplicate compatibility surface

### Meaning

Leave `GET /api/v1/appointments/stats` mounted and unchanged even though it
duplicates `queues.stats()`.

### Pros

- zero immediate compatibility risk
- no behavior change

### Risks

- keeps OnlineDay read surface wider than necessary
- preserves duplicate public contract
- delays deprecation of the legacy island

### Migration complexity

Low

## Option B — Redirect later to the same future read-model as `queues.stats`

### Meaning

Preserve the route path, but later make it read from the same future owner as
`queues.stats()`.

### Pros

- keeps compatibility path if somebody still uses the route
- removes duplicate legacy runtime ownership later

### Risks

- still preserves a duplicate public surface
- may spend engineering effort modernizing a route with no confirmed consumer

### Migration complexity

Medium

## Option C — Mark as deprecate-later candidate and prepare retirement

### Meaning

Treat the route as a mounted duplicate that should move toward retirement unless
real consumers are confirmed.

### Pros

- matches current evidence best
- reduces legacy surface intentionally
- avoids modernizing a contract with unclear value

### Risks

- still requires a careful transition because the route is public and mounted

### Migration complexity

Low to medium

## Option D — Retire immediately

### Meaning

Remove the route now.

### Pros

- fastest surface reduction

### Risks

- too aggressive for a mounted public route
- would skip deprecation prep
- external/manual usage has not been disproven

### Migration complexity

Medium, but with avoidable risk

## Recommended option

Option C is the best current fit:

- `appointments.stats()` should be treated as a deprecate-later duplicate read
  surface
- the next step should be narrow retirement/deprecation prep, not immediate
  removal and not read-model modernization
