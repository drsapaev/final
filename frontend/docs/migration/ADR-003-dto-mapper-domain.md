# ADR-003: DTO → Mapper → Domain type architecture

**Date:** 2026-07-17
**Status:** Accepted

## Context

The backend's OpenAPI spec describes `LoginResponse` as a flat nullable
superset:

```json
{
  "requires_2fa": "boolean",
  "pending_2fa_token": "string | null",
  "access_token": "string | null",
  "refresh_token": "string | null",
  ...
}
```

This is the **transport contract** — it says which fields MAY appear
in JSON. It does NOT express the **semantic invariant** from
`AUTHENTICATION_LAWS_FOR_AI.md` ЗАКОН 2:

> `requires_2fa === true` ⇒ `access_token` MUST NOT be present
> `requires_2fa === false` ⇒ `pending_2fa_token` MUST NOT be present

If we re-type the generated DTO to encode this invariant (e.g. as a
discriminated union), the typing would be lost on next regeneration
(see ADR-002). If we use the flat DTO directly, the invariant is
unenforceable — code could read `access_token` even when
`requires_2fa === true`.

## Decision

Three-layer architecture for types with business invariants:

```
HTTP JSON
    ↓
Generated DTO (src/types/generated/api.ts — read-only, flat nullable superset)
    ↓
Mapper (src/types/auth-mapper.ts — validates invariant, throws on violation)
    ↓
Domain Type (src/types/auth.ts — discriminated union, type-safe)
    ↓
UI / application code
```

**Layer 1 — Generated DTO (`*Raw` aliases in `api.ts`):**
- Reflects OpenAPI one-to-one
- All fields are nullable / optional per the spec
- Never edited by hand (ADR-002)

**Layer 2 — Mapper (`auth-mapper.ts`):**
- `parseLoginResponse(dto: LoginResponseRaw): LoginResult`
- Validates the invariant: if `requires_2fa === true` and
  `access_token` is present, throws `AuthInvariantViolationError`
- Returns the domain type (discriminated union)
- Also provides `tryParse*` Either-style wrappers for React render paths

**Layer 3 — Domain Type (`auth.ts`):**
- `LoginResult = LoginRequires2FA | LoginSucceeded` (discriminated union)
- Makes the invariant unrepresentable at the type level — there is no
  `LoginResult` value where both `access_token` and `pending_2fa_token`
  coexist
- Pure types, no imports from generated (no runtime dependency)

## Consequences

**Positive:**
- If the backend ever violates ЗАКОН 2 (e.g. returns
  `{ requires_2fa: true, access_token: "..." }`), the mapper throws
  `AuthInvariantViolationError` — surfacing the backend bug loudly
  instead of silently corrupting auth state.
- The generated DTO stays clean (matches OpenAPI exactly).
- The domain type is type-safe — TS narrows automatically when you
  check `if (result.requires_2fa) { ... }`.
- The architecture is generalizable: any domain entity with a business
  invariant (e.g. "Payment.status='paid' requires transaction_id")
  can follow the same pattern.

**Negative:**
- Extra layer of indirection (mapper function call).
- Mapper must be called at every API boundary — forgetting to call it
  means using the raw DTO, which is still type-valid but unsafe.
- Phase 9 should add an ESLint rule to ban direct use of `*Raw` types
  outside of mappers.

## Alternatives considered

1. **Re-type the generated DTO as discriminated union** — rejected.
   Would be overwritten on next regeneration (ADR-002). Conflates
   transport with semantics.

2. **Use the flat DTO directly, document the invariant in comments** —
   rejected. Comments don't enforce anything. The Phase 2-9 disaster
   showed that "discipline-based" approaches fail under time pressure.

3. **Runtime validation with Zod** — considered. More powerful than
   hand-written mappers, but adds a runtime dependency and is overkill
   for the current scope. Could be adopted in Phase 9 if the number of
   mappers grows.

## References

- `src/types/auth.ts` — domain types (LoginResult discriminated union)
- `src/types/auth-mapper.ts` — mappers + AuthInvariantViolationError
- `src/types/api.ts` — `*Raw` aliases (LoginResponseRaw, etc.)
- `src/api/client.ts` — `login()` uses `parseLoginResponse()`
- `docs/AUTHENTICATION_LAWS_FOR_AI.md` — ЗАКОН 2 (the invariant source)
