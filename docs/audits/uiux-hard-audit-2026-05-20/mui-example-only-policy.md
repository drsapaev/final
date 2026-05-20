# PR-MUI-3 Example-Only MUI Policy

Date: 2026-05-20

## Scope

Decision-only policy for the remaining MUI references in:

- `frontend/src/components/examples/UnifiedButton.tsx`
- `frontend/src/components/examples/UnifiedCard.tsx`

No runtime UI, route, backend, auth, RBAC, payment, queue, clinical, Telegram,
or notification behavior was changed.

## Static Evidence

Commands:

```powershell
rg -n "UnifiedButton|UnifiedCard|components/examples|examples/Unified" frontend\src
rg -n "@mui|Mui" frontend\src\components\examples\UnifiedButton.tsx frontend\src\components\examples\UnifiedCard.tsx
```

Result:

- `UnifiedButton.tsx` and `UnifiedCard.tsx` contained MUI imports at the time
  PR-MUI-3 was written.
- Static search did not find active app callers for `UnifiedButton` or
  `UnifiedCard`.
- `frontend/src/pages/MacOSDemoPage.jsx` lazy-loads
  `frontend/src/components/examples/MacOSDemo`, not these two MUI example
  components.

## Policy

The two `Unified*` example files are example-only MUI references, not active
clinic runtime UI debt.

They must not be used as source templates for new clinic screens because the
canonical app UI layer is:

- `frontend/src/components/ui/macos`
- `frontend/src/theme/macos-tokens.css`
- `frontend/src/theme/macosTheme.jsx`
- `frontend/src/styles/macos.css`

Default rule:

- Do not import `UnifiedButton.tsx` or `UnifiedCard.tsx` into app pages, role
  panels, workflow components, route views, payment/queue/clinical screens, or
  authenticated dashboards.
- Do not copy their MUI patterns into new clinic runtime UI.
- If either file becomes reachable from an active route, reclassify it from
  `example-only` to `runtime` and require a scoped migration or removal PR.
- Do not remove MUI dependencies only because these example files remain; MUI
  dependency removal remains blocked until runtime imports reach `0` and the
  example policy is separately enforced.

## Future Options

Choose one later, in a separate PR:

1. Convert the examples to macOS primitives and keep them as design-system
   reference examples.
2. Move them to archived/historical documentation if they are no longer useful.
3. Delete them if no docs, tests, or developer workflow references depend on
   them.

Do not combine that cleanup with payment, queue, admin, clinical, Telegram, or
AI/MCP MUI migration.

## Result

PR-MUI-3 does not reduce the raw `rg '@mui|Mui'` count. It clarifies that the
two `components/examples/Unified*` files are isolated reference debt and should
not block runtime UI decisions or be treated as safe app patterns.

## Follow-Up: UnifiedButton Example Migration

`frontend/src/components/examples/UnifiedButton.tsx` has since been converted
to a macOS/native example with no current `@mui` import. It remains example-only
and must not be imported into clinic runtime UI.

## Follow-Up: UnifiedCard Example Migration

`frontend/src/components/examples/UnifiedCard.tsx` has since been converted to
a macOS/native example with no current `@mui` import. It remains example-only
and must not be imported into clinic runtime UI.

The current example-only MUI count is now `0`; remaining MUI files are all
runtime domain islands that require dedicated gate/handoff slices.

## Next Smallest Step

Proceed to PR-MUI-4: create gated handoffs for payment, queue, lab, dental,
cardiology, patient, Telegram, and AI/MCP MUI islands without migrating those
riskier runtime surfaces in the same PR.
