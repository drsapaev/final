# Registrar Panel — Canonical Design System

> **Status**: macOS Design System is the single canonical system for the Registrar Panel.
> All other design systems (unified, TS tokens, Tailwind, legacy CSS) are deprecated.

## Audit Context

The UX audit (§5.6 Consistency, score 3/10) identified **six competing design systems** in the codebase:
1. macOS Design System (`--mac-*` tokens, `components/ui/macos/*`)
2. Unified Design System v2.0 (`--color-*` tokens, `theme/unifiedTheme.js`)
3. TS Tokens (`theme/tokens/colors.ts` — aspirational, never adopted)
4. Tailwind utility classes (scattered in a few components)
5. Legacy CSS classes (`clinic-button`, `hover-lift`, etc.)
6. Inline `style={{}}` blocks with hardcoded hex colors

**Strategic Direction 2** (audit §8) calls for choosing ONE design system. The macOS Design System was selected because:
- 38 components already written in `components/ui/macos/`
- `macos-tokens.css` (677 lines) is the most complete token file
- `styles/macos.css` (870 lines) provides comprehensive utility classes
- The `Unified` theme was an incomplete migration attempt

## Canonical Tokens (macOS)

### Primary Colors
| Token | Value | Use |
|---|---|---|
| `--mac-accent-blue` | `#007aff` | Primary actions, links, focus rings |
| `--mac-accent-blue-hover` | `#0051d5` | Hover state for primary actions |
| `--mac-accent-blue-active` | `#004bb5` | Active/pressed state |

### Semantic Colors
| Token | Value | Use |
|---|---|---|
| `--mac-success` | `#30d158` | Success states, "loaded from server" |
| `--mac-warning` | `#ff9f0a` | Warnings, "showing fallback data" |
| `--mac-error` / `--mac-danger` | `#ff453a` | Errors, "failed to load" |

### Text Colors
| Token | Value | Use |
|---|---|---|
| `--mac-text-primary` | `#000000` | Primary body text |
| `--mac-text-secondary` | `#455568` | Secondary text, captions |
| `--mac-text-tertiary` | `#5d6f84` | Muted text, placeholders |

### Background Colors
| Token | Value | Use |
|---|---|---|
| `--mac-bg-primary` | `#eef3fa` | Card backgrounds, primary surfaces |
| `--mac-bg-secondary` | `#e3ebf5` | Secondary surfaces, stripes |
| `--mac-bg-tertiary` | `#d7e1ee` | Tertiary surfaces |
| `--mac-bg-quaternary` | `#ccd8e7` | Quaternary surfaces, dark mode fallbacks |

### Border Colors
| Token | Value | Use |
|---|---|---|
| `--mac-border` | `#b8c8da` | Primary borders |
| `--mac-border-secondary` | `#cad8e7` | Lighter borders, dividers |
| `--mac-separator` | (defined in macos.css) | Separators between sections |

## Migration Status (Registrar Panel)

| Artifact | Before Audit | After DS-2 (this PR) |
|---|---|---|
| Hardcoded hex colors | 16 | **0** |
| `--color-*` variable usages | 8 | **0** |
| `--mac-*` variable usages | 100 | **127** |
| Legacy CSS classes (`clinic-button`, etc.) | 6 | **0** (removed in QW-01) |
| Inline `style={{}}` blocks | 96 | 97 (DS-2 only changed values, not structure) |

## What Changed in DS-2

### Hardcoded hex → macOS tokens

| Hex | macOS Token | Context |
|---|---|---|
| `#f3f4f6` | `var(--mac-bg-secondary)` | Light mode background |
| `#4b5563` | `var(--mac-bg-quaternary)` | Dark mode background |
| `#10b981` | `var(--mac-accent-green)` | Success button background |
| `#059669` | `var(--mac-accent-green-hover)` | Success button hover |
| `#6b7280` | `var(--mac-text-tertiary)` | Gray button background |
| `#4b5563` | `var(--mac-text-secondary)` | Gray button hover |
| `#e5e7eb` | `var(--mac-border-secondary)` | Light mode border |
| `#374151` | `var(--mac-bg-quaternary)` | Dark mode border |
| `#9ca3af` | `var(--mac-text-tertiary)` | Muted text |
| `#ffffff` | `var(--mac-bg-primary)` | White background |
| `#ef4444` / `#dc2626` gradient | `var(--mac-error)` | Error state gradient |
| `#3b82f6` / `#2563eb` gradient | `var(--mac-accent-blue)` | Loading state gradient |
| `#3b82f6` / `#1d4ed8` gradient | `var(--mac-accent-blue)` | "Load more" button gradient |

### `--color-*` → `--mac-*` variables

| Old (unified) | New (macOS) | Variable |
|---|---|---|
| `var(--color-background-primary)` | `var(--mac-bg-primary)` | `cardBg` |
| `var(--color-background-secondary)` | `var(--mac-bg-secondary)` | `cardBg` |
| `var(--color-text-primary)` | `var(--mac-text-primary)` | `textColor` |
| `var(--color-border-medium)` | `var(--mac-border)` | `borderColor` |
| `var(--color-border-light)` | `var(--mac-border-secondary)` | `borderColor` |
| `var(--color-primary-500)` | `var(--mac-accent-blue)` | `accentColor` |
| `var(--color-primary-600)` | `var(--mac-accent-blue-hover)` | Tooltip background |

## What's NOT Changed (Deferred)

### Inline `style={{}}` blocks (97 remaining)

The 97 inline style blocks remain. They are now using macOS tokens (no hardcoded hex), but the structure is still inline. Full migration to CSS classes would require:
1. Creating a `registrar.css` with named classes for each style pattern
2. Replacing `style={{...}}` with `className="registrar-..."` 
3. Adding ESLint rule `react-native/no-inline-styles` to prevent regression

This is a larger effort (estimated 2-3 days) and is deferred to a follow-up PR.

### Other panels (AdminPanel, CashierPanel, etc.)

This PR only addresses the Registrar Panel. Other panels still have:
- AdminPanel.jsx: 260 inline style blocks
- DentistPanelUnified.jsx: 265 inline style blocks
- DermatologistPanelUnified.jsx: 171 inline style blocks

These will be migrated one panel at a time in follow-up PRs.

## ESLint Enforcement (Future)

To prevent regression, the following ESLint rule should be added to `.eslintrc`:

```json
{
  "rules": {
    "no-restricted-syntax": [
      "warn",
      {
        "selector": "Literal[value=/^#[0-9a-fA-F]{3,8}$/]",
        "message": "Use macOS design tokens (var(--mac-*)) instead of hardcoded hex colors"
      }
    ]
  }
}
```

This is deferred because it would currently trigger warnings in other panels that haven't been migrated yet.

## Verification

Run this command to verify the Registrar Panel uses only macOS tokens:

```bash
python3 -c "
import re
with open('frontend/src/pages/RegistrarPanel.jsx') as f:
    content = f.read()
hex = re.findall(r'#[0-9a-fA-F]{3,8}', content)
color_vars = re.findall(r'var\(--color-', content)
mac_vars = re.findall(r'var\(--mac-', content)
print(f'Hardcoded hex: {len(hex)} (expected: 0)')
print(f'--color-* vars: {len(color_vars)} (expected: 0)')
print(f'--mac-* vars: {len(mac_vars)} (expected: >100)')
"
```
