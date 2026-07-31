# Runtime Correctness Roadmap

**Status:** Planning
**Created:** 2026-07-31
**Author:** operator (Z) + user direction
**Depends on:** ADR-0013, ADR-0014, ADR-0015, ADR-0016, ADR-0017, ADR-0018

---

## Maturity assessment (current state)

The JS → TS migration is complete. The codebase has moved past "make
TypeScript happy" into architectural consolidation. Further work should
target **runtime correctness**, not "more typing".

| Stage | Status |
|-------|--------|
| JS → TS | ✅ Complete |
| Strict typing | ✅ Complete (`strict:true`, 0 tsc errors, 0 `@ts-nocheck`) |
| Domain modeling | ✅ Complete (branded IDs, mappers, domain types in `types/domain/`) |
| Boundary architecture | ✅ Complete (ADR-0015; 23 → 3 runtime violations, all exempt) |
| Runtime validation | 🟡 Started (ADR-0018 written; mapper adoption is incremental, not yet started) |
| Domain invariants | ⏳ Next |
| Workflow verification | ⏳ Next |
| Property-based / invariant testing | ⏳ After |

---

## Refined evaluation criteria

The audit no longer evaluates by raw grep counts. These 4 refinements
replace "lower is better" with "localized and justified is better".

### 1. `Record<string, unknown>` is NOT automatically tech debt

`Record<string, unknown>` is the correct type at boundaries for:
- backend metadata fields (e.g. `session.metadata`)
- plugin / MCP payloads (free-form JSON)
- arbitrary JSON from external systems
- Zod schema catch-all output
- WebSocket message envelopes before parsing

**The right question is not "how many?"** but **"are they only at boundaries?"**
A `Record<string, unknown>` inside a Domain type (e.g. `Patient` with a
`metadata: Record<string, unknown>` field that components read directly)
is a smell. A `Record<string, unknown>` in a DTO or mapper input is
correct.

### 2. `as` is NOT a target for "zero"

A mature TS project always retains `as` for:
- branded type factories (`as BrandedId`)
- DOM casts (`event.target as HTMLInputElement`)
- React refs (`ref.current as T`)
- boundary mappers (`dto as DomainType` after validation)
- integration points with untyped libraries

**The right question is not "how many?"** but **"are they localized and
justified?"** The 20 accepted `as` casts in the codebase (per type-debt
baseline) all have `TECH-DEBT(...)` markers explaining why. That is the
correct state.

### 3. `String()` needs semantic classification, not counting

| Pattern | Verdict |
|---------|---------|
| `String(err)` | ✅ Normal — error coercion |
| `String(id)` | ✅ Normal — ID normalization for URL/log |
| `String(value ?? '')` | ✅ Normal — null-safe rendering |
| `String(patient.birthDate)` | ⚠️ Smell — birthDate should already be a typed `string` or `Date`; coercing it suggests a lost type upstream |
| `String(data.field)` where `data: Record<string, unknown>` | ✅ Normal — boundary coercion from unknown |

**The right question is not "how many `String()` calls?"** but **"is the
coercion at a boundary (correct) or masking a lost domain type (smell)?"**

### 4. `!` (non-null assertion) is the most dangerous — every one must be provable

`!` is where the audit is strictest. Not the count — the **proof**.
Every remaining `!` must have a `SAFETY:` comment explaining why the
value is non-null at this point.

```typescript
// ✅ Good — provable
const patient = patients.find(p => p.id === id)!;
// SAFETY: filtered above by `patients.some(p => p.id === id)` check at line 42

// ✅ Good — provable
const node = ref.current!;
// SAFETY: useEffect at line 18 guarantees ref.current is set before this callback runs

// ❌ Bad — unprovable
const patient = patients[0]!;
// No justification — what if patients is empty?
```

**The right question is not "how many `!`?"** but **"does every `!`
have a SAFETY comment that a reviewer can verify?"**

---

## Three tracks for runtime correctness

These are independent — each can proceed at its own pace. The natural
priority order is Boundary → Domain → Workflow, because each builds on
the previous.

### Track 1 — Boundary correctness (highest priority)

**Goal:** catch backend contract drift at the application edge, not in
component render.

Already started by ADR-0018. This track continues it.

**Scope:**
- DTO validation via Zod schemas in `api/mappers/*.ts`
- Mapper validation (the single boundary per ADR-0018)
- Invariant checks on Domain types after mapping
- WebSocket message validation (already partially done in `utils/ws-schemas.ts`)

**Concrete first step:** pick the highest-risk mapper (likely
`api/mappers/patients.ts` — patient data is critical for EMR), add a
Zod schema for `PatientDTO`, add `schema.parse(dto)` at the top of
`mapPatient`, unit-test with valid + invalid fixture DTOs.

**Why highest priority:** this is where production bugs actually
appear. A backend field rename (`first_name` → `firstName`) silently
propagates through `as` casts and crashes a component far from the
source. Zod at the mapper turns that into an immediate, actionable
error at the boundary.

### Track 2 — Domain correctness

**Goal:** enforce business invariants, not just types.

**Scope — example invariants to codify:**
- `Appointment.patient_id` MUST reference an existing `Patient`
- `Visit` cannot be completed twice (terminal state)
- `Payment.amount` MUST be ≥ 0
- `EMR` cannot be signed without required fields (complaints, diagnosis)
- `Invoice` cannot be paid after cancellation
- `QueueEntry` cannot be called after `completed` status

**Implementation approach:**
- Add invariant checks in Domain constructors / factories
- Or: add a `validate()` method on Domain types that mappers call after mapping
- Or: Zod refinements (`z.string().refine(...)`) for simple invariants

**Why second:** boundary correctness (Track 1) catches shape errors;
domain correctness catches semantic errors. You need both — a
well-shaped `Payment` with `amount: -100` passes shape validation but
violates a business rule.

### Track 3 — Workflow correctness

**Goal:** verify state machines are correct and cannot reach illegal
states.

**Scope:**
- `useEMR` reducer: `draft → dirty → saving → saved → conflict → readonly → autosaving`
- `useAIChat` ChatSessionState: already covered by ADR-0017 (107 tests)
- `useAppointments`: implicit state machine (`pending → confirmed → completed / cancelled`)
- `Payment` lifecycle: `pending → paid / cancelled / refunded`
- `QueueEntry`: `waiting → called → serving → completed / skipped`

**Implementation approach:**
- Extract transition tables (like `isValidConnectionTransition` for ChatSessionState)
- Add table-driven property tests (reachability, forbidden-edge rejection, no-dangling, idempotency)
- For `useReducer`-based workflows, add a transition validator that the reducer calls before applying

**Why third:** workflow bugs are rarer than boundary or domain bugs,
but when they occur they corrupt data silently (e.g. a Visit stuck in
`saving` forever, or a Queue that lets a `completed` entry be `called`
again). This track is the natural extension of ADR-0017 to the rest of
the codebase.

---

## What this roadmap explicitly does NOT do

- ❌ Try to drive `as` / `String()` / `Record<string, unknown>` counts to zero
- ❌ Add Zod schemas to every endpoint in one sprint (incremental adoption)
- ❌ Replace `useReducer` with Zod-validated state machines
- ❌ Introduce a global invariant engine or OOP-style Domain classes
- ❌ Any change that does not trace to a concrete correctness gap

---

## Natural order vs. parallel tracks

The three tracks are **independent** — work on one does not block
another. But the natural priority is:

1. **Boundary first** — catches the most common production bugs
   (contract drift). Already started (ADR-0018).
2. **Domain second** — catches semantic bugs that pass shape validation.
   Builds on Track 1 (mappers emit validated Domain types; Track 2
   adds invariant checks on those Domain types).
3. **Workflow third** — catches state-machine bugs. Builds on Track 2
   (Domain invariants constrain what transitions are legal).

Property-based / invariant testing (the maturity table's last row) comes
after all three tracks have initial coverage — it stress-tests the
invariants and transition tables with generated inputs.

---

## Reference

- ADR-0013 — State Management Boundaries
- ADR-0014 — State Pattern Matrix
- ADR-0015 — Domain Boundary Matrix (runtime boundary cleanup complete)
- ADR-0016 — Error Taxonomy (P0 consolidation complete)
- ADR-0017 — Transition Verification (ChatSessionState; EMR + others are Track 3)
- ADR-0018 — Runtime Validation Strategy (Track 1 foundation)
- This document: `docs/architecture/ROADMAP-runtime-correctness.md`
