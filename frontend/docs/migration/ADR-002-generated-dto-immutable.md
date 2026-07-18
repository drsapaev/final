# ADR-002: Generated DTO types are immutable

**Date:** 2026-07-17
**Status:** Accepted

## Context

`openapi-typescript` generates `src/types/generated/api.ts` (75K lines)
from `backend/openapi.json`. Without protection, developers might edit
this file directly to fix a type mismatch or add a missing field —
and those edits would be silently lost on the next regeneration.

## Decision

Generated files in `src/types/generated/` are **read-only**:

1. **Header warning** — the file starts with `⚠️ АВТОГЕНЕРИРОВАННЫЙ ФАЙЛ — НЕ РЕДАКТИРОВАТЬ ВРУЧНУЮ!`
2. **ESLint ignore** — `src/types/generated/**` is excluded from linting
3. **`.gitattributes`** — `frontend/src/types/generated/** linguist-generated=true` so GitHub doesn't count it in PR diffs
4. **CI gate** — `npm run generate:api-types:check` fails if the committed file doesn't match a fresh regeneration
5. **Import policy** — app code imports from `@/types/api` (the re-export layer), NOT from `@/types/generated/api` directly. (Phase 9 will add an ESLint `no-restricted-imports` rule to enforce this.)

## Consequences

**Positive:**
- No risk of silent loss — CI catches any drift.
- PR diffs stay clean (linguist-generated hides the 75K lines).
- Clear boundary: generated = transport contract, manual = domain logic.

**Negative:**
- If the backend OpenAPI spec is wrong, the generated types will be
  wrong too. Fixing this requires a backend change, not a frontend edit.
- The 75K-line file is large — `skipLibCheck: true` in tsconfig mitigates
  compile-time impact.

## Alternatives considered

1. **Allow hand-edits with a `.patch` file** — rejected. Too clever,
   breaks contributor onboarding, patch could go stale.

2. **Filter generated types to only what frontend uses** — considered
   for future optimization. Vite's tree-shaking handles this at build
   time; `skipLibCheck` handles it at compile time. Not needed now.

## References

- `scripts/generate-api-types.sh` — adds the header warning
- `eslint.config.js` — `ignores: ['src/types/generated/**']`
- `.gitattributes` — `linguist-generated=true`
- `package.json` — `generate:api-types:check` script
- `src/types/api.ts` — re-export layer (the public API for app code)
