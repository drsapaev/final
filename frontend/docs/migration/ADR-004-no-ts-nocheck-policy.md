# ADR-004: No @ts-nocheck policy

**Date:** 2026-07-17
**Status:** Accepted

## Context

During Phase 2-9 of the JS→TS migration, `@ts-nocheck` was used as a
pragmatic shortcut to convert `.js` → `.ts` without actually typing
the code. The result:

- **481 of 772 files** (62.3%) had `@ts-nocheck`
- **7+ files** had semantic damage from regex patches that `@ts-nocheck`
  masked (the regex changed destructuring semantics, but TypeScript
  couldn't catch it because the check was disabled)
- **96 ESLint errors** existed but were masked or ignored
- **864 tests passed** — but the tests didn't cover the damaged paths,
  so "all tests pass" gave false confidence

The project was structurally TypeScript (all files had `.ts`/`.tsx`
extensions) but functionally untyped (62% of files disabled the type
checker). This is worse than no migration at all — it creates the
illusion of migration while providing none of the safety.

## Decision

`@ts-nocheck` is **forbidden** in new code:

1. **No new `@ts-nocheck`** — every migrated file must pass `tsc --noEmit`
   cleanly (0 errors) without disabling the type checker.
2. **Existing `@ts-nocheck` is tracked** — the Type Debt Register (B5)
   counts `@ts-nocheck` files. The count must be 0 at all times.
3. **Phase 2-redo** will not use `@ts-nocheck`. Files are migrated in
   batches of 5-10 with proper typing, not 61 at once with `@ts-nocheck`.

## Consequences

**Positive:**
- TypeScript actually checks the code — semantic damage from regex
  patches would be caught immediately.
- The migration is honest — "110 files migrated" means 110 files are
  type-checked, not 110 files were renamed.
- Slow migration forces understanding of the code before typing it.

**Negative:**
- Migration is slower (30-60 minutes per file vs. 5 seconds per file
  with `@ts-nocheck`).
- Some files may be genuinely hard to type (e.g. `panelPrint.ts` with
  1140 lines of heterogeneous shapes). These are tracked in the Type
  Debt Register with ⚠️ Legacy category and `any` typing — but NOT
  `@ts-nocheck`. The file is still type-checked; it just uses `any`
  for the parts that are too complex to type properly.

**Exception policy:**
- `@ts-nocheck` is allowed ONLY for:
  1. Third-party type definition files that are broken and can't be fixed
     upstream (extremely rare)
  2. Temporary debugging (must be removed before merge)
- Each exception must be documented in the Type Debt Register with
  a justification and an expected resolution date.

## Alternatives considered

1. **Allow `@ts-nocheck` with a register entry** — rejected. The
   Phase 2-9 disaster showed that register discipline fails in
   practice: the count grew from 0 to 481 in a single session because
   "just add `@ts-nocheck` and move on" was too tempting.

2. **Use `// @ts-expect-error` per-line instead of file-level `@ts-nocheck`** —
   acceptable for genuine type errors that can't be fixed immediately,
   but each occurrence must be registered in B5 with a reason. Better
   than `@ts-nocheck` because it's scoped to a specific line, not the
   whole file.

3. **Allow `@ts-nocheck` but run `tsc` with `--skipLibCheck` to speed
   up** — irrelevant. `--skipLibCheck` skips declaration file checking,
   not source file checking.

## References

- `MIGRATION_BLOCKERS.md` — B3 (no @ts-nocheck), B5 (Type Debt Register)
- Phase 2-9 PRs (#2400-#2407) — the disaster that motivated this ADR
- Stabilization Sprint commit — reset to Phase 1 baseline (0 @ts-nocheck)
