# ADR-0018 — Runtime Validation Strategy

**Status:** Accepted
**Created:** 2026-07-31
**Depends on:** ADR-0013, ADR-0014, ADR-0015, ADR-0016

## Summary

Defines **where** runtime validation happens in the frontend data flow, and
**what** each layer is responsible for validating. The goal is to catch
backend contract drift early (at the application boundary) instead of late
(in component render), without forcing every layer to re-validate.

## Context

The codebase has four layers between the network and the UI:

```
HTTP response
   ↓
api/client.ts          (axios instance + interceptors)
   ↓
api/<resource>.ts      (REST functions, e.g. api/patients.ts)
   ↓
api/mappers/*.ts       (DTO → Domain transformation)
   ↓
hooks/*.ts             (state management)
   ↓
components/*.tsx       (rendering)
```

Before this ADR, runtime validation was ad-hoc:
- `api/client.ts` supports an optional `schema` param (zod), but no caller uses it
- `utils/ws-schemas.ts` has zod schemas for WebSocket messages, used by `useAIChat`
- Mappers do `as` casts (no validation)
- Hooks trust whatever mappers return
- Components trust whatever hooks return

This means a backend contract change (e.g. `id: number` → `id: string`)
would silently propagate through mappers and hooks, and only fail when a
component tries `patient.id.toFixed(0)` — at which point the error
message is opaque ("toFixed is not a function") and far from the source.

## Decision

### Single validation boundary: the mapper layer

**Validation happens ONCE, at the mapper layer** (`api/mappers/*.ts`).
Every mapper that transforms a DTO to a Domain type MUST validate the DTO
shape before (or during) transformation.

```
HTTP response (raw JSON)
   ↓  (no validation — axios just parses JSON)
api/client.ts
   ↓  (no validation — REST function passes raw DTO to mapper)
api/<resource>.ts
   ↓  ★ VALIDATION HERE ★
api/mappers/*.ts        (zod schema validates DTO, then transforms to Domain)
   ↓  (Domain type is trusted — no re-validation)
hooks/*.ts
   ↓  (no validation — component trusts Domain)
components/*.tsx
```

### Why the mapper layer

1. **Single source of truth.** The mapper is the only place where DTO
   and Domain coexist. Validating here means the schema is co-located
   with the transformation it guards.

2. **Fail fast, fail loud.** A validation failure in the mapper produces
   an error like "PatientDTO.id expected number, received string" —
   immediate, actionable, close to the source.

3. **No re-validation.** Once the mapper emits a Domain value, every
   downstream layer (hook, component) can trust the type. This avoids
   the anti-pattern of every layer re-checking the same fields.

4. **Testable in isolation.** Mappers are pure functions; their zod
   schemas can be unit-tested with fixture DTOs without spinning up
   React or axios.

### What each layer validates (or doesn't)

| Layer | Validates | Does NOT validate |
|-------|-----------|-------------------|
| `api/client.ts` | HTTP status (via interceptors); auth token freshness | Response body shape |
| `api/<resource>.ts` | Nothing (passes raw DTO to mapper) | Domain shape |
| `api/mappers/*.ts` | **DTO shape via zod schema** (the one validation boundary) | Domain invariants (those are the Domain type's job) |
| `hooks/*.ts` | Nothing (trusts Domain from mapper) | Re-validation |
| `components/*.tsx` | UI input (form fields) | API response shape |

### WebSocket validation

WebSocket messages are validated at the **message handler** in
`useAIChat.ts`, using the schemas in `utils/ws-schemas.ts`. This is a
separate boundary because WebSocket messages don't go through mappers —
they arrive as raw JSON and are dispatched by `handleWebSocketMessage`.

```
WS message (raw JSON)
   ↓  ★ VALIDATION HERE ★
useAIChat.ts:handleWebSocketMessage  (zod schema from utils/ws-schemas.ts)
   ↓  (trusted message shape)
state update
```

### Form input validation

Form input is validated at the **component** layer, using the existing
`validators` and `validateForm` utilities in `utils/errorHandler.ts`.
This is a separate concern from API response validation — form input is
user-generated, not backend-generated.

```
User types in form
   ↓  ★ VALIDATION HERE ★
component (validators / validateForm)
   ↓  (validated input)
hook (sends to API)
```

## Concrete implementation guide

### For mappers (the main validation boundary)

```typescript
// api/mappers/patients.ts
import { z } from 'zod';
import type { Patient } from '../../types/domain/clinic';

// 1. Define the DTO schema (matches backend OpenAPI spec)
const PatientDtoSchema = z.object({
  id: z.union([z.number(), z.string()]),
  first_name: z.string(),
  last_name: z.string(),
  phone: z.string(),
  // ... other fields
});

// 2. The mapper validates, then transforms
export function mapPatient(dto: unknown): Patient {
  const parsed = PatientDtoSchema.parse(dto);  // throws ZodError on mismatch
  return {
    id: parsed.id,
    firstName: parsed.first_name,
    lastName: parsed.last_name,
    phone: parsed.phone,
  };
}
```

### When to use `safeParse` vs `parse`

- **`parse`** (throws): use when the DTO MUST be valid — a failure means
  the backend broke its contract and the request is unrecoverable.
- **`safeParse`** (returns `{ success, data, error }`): use when you
  want to gracefully degrade (e.g. log the error but still render
  partial data with fallbacks).

Default to `parse`. Use `safeParse` only when the mapper has a documented
fallback strategy.

### For new endpoints

When adding a new API endpoint:
1. Define the DTO zod schema in `api/mappers/<resource>.ts`
2. The mapper validates the DTO, then transforms to Domain
3. The REST function in `api/<resource>.ts` calls the mapper
4. The hook consumes the Domain type — no validation needed
5. The component consumes the hook's return — no validation needed

### For existing endpoints (migration)

Migrate incrementally. Pick the most failure-prone endpoint first (e.g.
one that has caused production bugs), add a zod schema + validation to
its mapper, and ship. Repeat for other endpoints over time.

**This is NOT a big-bang migration.** The boundary is defined; adoption
is incremental.

## What this ADR does NOT prescribe

1. **No re-validation at the component layer.** Components trust Domain
   types. If a component feels the need to validate, the mapper is
   broken — fix the mapper, don't add component-level validation.

2. **No global schema registry.** Schemas live next to their mappers.
   If two mappers need the same sub-schema (e.g. `AddressSchema`),
   extract it to a shared file under `api/mappers/schemas/` — but only
   when there's actual duplication, not preemptively.

3. **No validation of outgoing requests.** The frontend validates
   responses, not requests. The backend is responsible for rejecting
   malformed requests with 400/422.

4. **No removal of TypeScript types.** Zod schemas complement TypeScript
   types; they don't replace them. The mapper's return type is still
   `Patient` (Domain), and TypeScript still catches static type errors
   at compile time. Zod catches runtime shape errors that TypeScript
   cannot (because the backend contract is not enforced at compile time).

## Current state (2026-07-31)

- ✅ `zod` installed (`zod@^4.4.3`)
- ✅ `utils/ws-schemas.ts` — zod schemas for WebSocket messages (used by `useAIChat`)
- ✅ `api/client.ts` — supports optional `schema` param in `apiRequest` (unused by callers)
- ⏳ Mappers — no zod schemas yet; all use `as` casts
- ⏳ No zod schemas for REST DTOs

## Next steps (incremental, not blocking)

1. Pick the highest-risk mapper (e.g. `api/mappers/patients.ts` —
   patient data is critical for the EMR flow).
2. Add a zod schema for the PatientDTO.
3. Add `schema.parse(dto)` at the top of `mapPatient`.
4. Unit-test the mapper with valid + invalid fixture DTOs.
5. Ship. Monitor for validation failures in production.
6. Repeat for the next mapper.

The goal is **not** to validate every endpoint in one sprint. The goal is
to establish the boundary (this ADR) and migrate incrementally — one
mapper at a time, prioritized by risk.

## Rule of thumb

> "Validate at the boundary, trust everywhere else. The mapper is the
> boundary. If you're validating in a component, you're validating too
> late."

This ADR is the single source of truth for runtime validation strategy.
ADR-0013 explains state patterns; ADR-0015 explains import boundaries;
ADR-0016 explains error shapes; ADR-0017 explains state transitions;
ADR-0018 explains where validation lives.
