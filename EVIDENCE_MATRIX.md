# Evidence Matrix

```
Scope:
  Repository: final (submodule)
  Branch:     phase-g2d-cashier-panel
  Commit:     41bf93da (strict fixes after merge with origin/main)
  Date:       2026-07-26
  Previous:   7b2f13c6934719d86f9fa6eadbf8800578eacdb0 (2026-07-25)
              — original Evidence Matrix; claims 1-2 have since been
              revised to FALSE after re-verification.
```

## How to read this document

Each row is a **falsifiable claim** about the codebase at the commit above.
"Verified" means the evidence was checked at that commit.
"Missing" means the artifact does not exist on this branch.

**Mechanism levels:**
- **Compiler** — TypeScript rejects invalid code at compile time. Cannot be bypassed without `as any` or `@ts-ignore`.
- **Lint** — ESLint rule rejects pattern. Can be bypassed with `eslint-disable`.
- **Observation** — Repository state at this commit. No automated enforcement. Can regress at any time.
- **Convention** — Team agreement. No automated check.

---

## Claims

| # | Claim | Mechanism | Verified | Evidence | How to reproduce |
|---|-------|-----------|----------|----------|------------------|
| 1 | CancelDialog accepts `Appointment \| null`, not arbitrary objects | Compiler | ✅ Verified | `CancelDialog.tsx:11` imports `Appointment` from `domain/clinic.ts` and the props interface uses `appointment: Appointment \| null`. The previous `TECH-DEBT(g2d-dialogs-001)` markers are removed (issue #2547). Boundary coercion `appointment.services as string[]` replaced with explicit `.map((s) => ...)` per-item rendering since `Appointment.services` is typed as `Array<{ name?: string; code?: string }>`. | `rg "appointment:" src/components/dialogs/CancelDialog.tsx` |
| 2 | PaymentDialog accepts `Appointment \| null` | Compiler | ✅ Verified | Same as #1. `PaymentDialog.tsx:13` has the live `Appointment` import; props interface uses `Appointment \| null`. `TECH-DEBT(g2d-dialogs-001)` removed. | `rg "appointment:" src/components/dialogs/PaymentDialog.tsx` |
| 3 | `colors.primary` typed as `Record<number, string>`, not `string` | Compiler | ✅ | `LoginFormStyled.tsx:362` — `(colors.primary as Record<number, string>)[500]`. Previous `as string[500]` (500th character) replaced. | `rg "as Record<number, string>" src/components/auth/LoginFormStyled.tsx` |
| 4 | Post-2FA catch block logs error instead of silent swallow | Observation | ✅ | `LoginFormStyled.tsx:288` — `logger.warn('[AUTH] Post-2FA navigation error...', post2FAError)` | `rg "Post-2FA" src/components/auth/LoginFormStyled.tsx` |
| 5 | `ui/macos/` contains zero `import PropTypes` | Observation | ✅ | `rg -l "PropTypes" src/components/ui/macos/` returns 0 files. All 45 files use TypeScript Props interfaces. **No automated enforcement** — PropTypes import can be re-added without error. | `rg -l "PropTypes" src/components/ui/macos/` |
| 6 | ActionButton requires `entry` prop | Compiler | ❌ **False** | `QueueManagementCard.tsx:101` — `entry: Record<string, unknown> \| null \| undefined`. `entry` accepts `null` and `undefined`, so `<QueueActionButtons entry={null} />` compiles. It is **not** a required non-null prop. | `npx tsc` with `<QueueActionButtons entry={null} />` — compiles successfully |
| 7 | `ElementType` rejects non-component values (e.g. numbers) | Compiler | ✅ | `Typography.tsx:9` — `component?: string \| React.ElementType`. Negative test: `<Test icon={123} />` → `TS2322: Type 'number' is not assignable to type 'ElementType'`. | Create temp file with `icon={123}`, run `npx tsc --noEmit` |
| 8 | `types/auth.ts` still exists (G6 legacy cleanup not merged) | Observation | ✅ (file exists) | `wc -l src/types/auth.ts` → 165 lines. This is a **legacy shim** — G6 cleanup was done on another branch. | `wc -l src/types/auth.ts` |
| 9 | `types/auth-store.ts` still exists | Observation | ✅ (file exists) | 48 lines. Same as #8. | `wc -l src/types/auth-store.ts` |
| 10 | `api/mappers/` directory exists | — | ❌ Missing | Directory does not exist on this branch. G4 Wave 4 work is on `phase-g3g-emr-completion`. | `ls src/api/mappers/` |
| 11 | ESLint rule `no-domain-type-duplication` exists | — | ❌ Missing | File `scripts/no-domain-type-duplication.js` does not exist. G4 Wave 5 not merged. | `ls scripts/no-domain-type-duplication.js` |
| 12 | ESLint rule `no-dto-import-in-components` exists | — | ❌ Missing | Same as #11. | `ls scripts/no-dto-import-in-components.js` |
| 13 | `tsconfig.strict.json` exists | — | ❌ Missing | G7 work not merged. | `ls tsconfig.strict.json` |
| 14 | `domain/ai.ts`, `domain/chat.ts`, `domain/mcp.ts` exist | — | ❌ Missing | G4 Wave 1 not merged. | `ls src/types/domain/ai.ts` |
| 15 | DTO types in `api.ts` have `*Dto` suffix | — | ❌ Missing | `api.ts:45` exports `Appointment`, not `AppointmentDto`. G4 Wave 3 not merged. | `grep "export type.*Appointment" src/types/api.ts` |

---

## Summary

| Category | Count |
|---|---:|
| Verified claims (compiler-enforced) | 2 |
| Verified claims (observation only) | 3 |
| Verified but weaker than claimed | 0 |
| **False claims (corrected in this revision)** | **2** |
| Missing artifacts | 8 |
| **Total claims** | **15** |

### Claims that were weaker than originally stated

**Claims 1-2 (Appointment in dialogs) — RESOLVED to TRUE:**
- Original claim (commit `7b2f13c6`): "CancelDialog/PaymentDialog accept `Appointment | null`"
- Was reverted (commit `0d2f95e3`) because applying `Appointment | null` cascaded into ~20 caller errors.
- **Now fixed (issue #2547)**: Both dialogs use `appointment: Appointment | null`. The cascading errors were resolved by (a) typing `cancelDialog` and `paymentDialog` state in `RegistrarPanel.tsx` with `Appointment | null` rows, and (b) casting the wizard-built row (`postWizardPaymentRow`) at its single call site since its builder returns `Record<string, unknown>`.
- `TECH-DEBT(g2d-dialogs-001)` markers removed.
- `tsc --noEmit` baseline: 72 errors → 72 errors (0 new).

**Claim 6 (ActionButton requires entry):**
- Original claim: "impossible to call ActionButton without onClick"
- Reality: `entry` accepts `null | undefined`, and `onStatusChange` is optional. `<QueueActionButtons entry={null} />` compiles. The claim was false.
- Fix needed: Make `entry` required and non-nullable, or change claim to "ActionButton props are explicitly typed."

### What actually prevents regression on this branch

| Mechanism | What it prevents | Can be bypassed? |
|---|---|---|
| TypeScript compiler | Passing wrong type to dialog props, non-ElementType to icon | Yes, via `as any` |
| Repository observation | PropTypes in ui/macos (currently zero) | Yes, no CI check |
| Nothing | New local Appointment-like interfaces | Yes, no ESLint rule |
| Nothing | Re-adding PropTypes | Yes, no lint rule |

### What would prevent regression after merging G4-G8

| Mechanism | What it prevents | Can be bypassed? |
|---|---|---|
| ESLint `no-domain-type-duplication` | New `interface Patient` outside domain | Yes, via `eslint-disable` |
| ESLint `no-dto-import-in-components` | Component importing `PatientDto` | Yes, via `eslint-disable` |
| ESLint `no-api-loose-return` | API function returning `any` without justification | Yes, via `eslint-disable` or `@api-transport` tag |
| CI strict-gate | Strict-ready directories regressing | Yes, by removing from `tsconfig.strict.json` |
| TypeScript compiler | Wrong prop types, non-ElementType | Yes, via `as any` |

**None of these are absolute guarantees.** All can be bypassed. The question is: how much friction does each add to regressing?
