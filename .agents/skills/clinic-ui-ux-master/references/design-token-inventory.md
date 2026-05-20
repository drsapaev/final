# Design Token Inventory

Use this reference when auditing CSS, tokens, palettes, typography, spacing, shadows, radii, or design-system drift.

## Goal

Build evidence before changing styles. The project already has a design system; inventory should reveal drift and convergence opportunities, not invent a new visual language.

## Inventory Categories

Collect:

- CSS variables and token names
- hardcoded colors
- font sizes and weights
- spacing values
- border radii
- shadows/elevation
- z-index values
- status color usage
- component imports
- legacy classes
- inline style hotspots

## Static Searches

Use:

```powershell
rg -n "--mac-|var\\(--|DESIGN_SYSTEM|tokens" frontend/src frontend/*.md
rg -n "#[0-9a-fA-F]{3,8}|rgb\\(|rgba\\(|hsl\\(" frontend/src
rg -n "fontSize|font-size|fontWeight|font-weight|letterSpacing|letter-spacing" frontend/src
rg -n "borderRadius|border-radius|boxShadow|box-shadow|zIndex|z-index" frontend/src
rg -n "style=\\{\\{|legacy-|@mui/" frontend/src
```

Use counts to prioritize, then inspect actual files.

## Palette Review

Check:

- dominant colors are not one-note
- status colors are consistent
- dark/light theme tokens map correctly
- hardcoded colors do not bypass theme
- disabled and secondary text remain readable
- links/actions are distinguishable from status text

Clinic caution:

- avoid aggressive purple/blue gradients as the dominant product feel
- avoid low-contrast muted text for clinical facts
- avoid using red for non-error decoration

## Typography Review

Check:

- page, panel, card, table, and label typography have clear hierarchy
- compact panels do not use hero-scale headings
- table text remains readable
- numbers and units are consistent
- no negative letter spacing
- no viewport-scaled type
- localized strings wrap cleanly

Prefer existing typography variables and component variants.

## Spacing And Layout Review

Check:

- repeated spacing values align with tokens
- grid gaps are consistent
- page shells are not implemented differently per role without reason
- card padding is stable
- forms use predictable vertical rhythm
- tables and toolbars align with role workflow

Do not standardize spacing mechanically if a clinical workflow needs density.

## Radius And Elevation

Check:

- cards use project-standard radius/elevation
- nested cards do not create noisy depth
- shadows do not hide focus rings or borders
- modals and popovers use consistent elevation
- status surfaces do not look like unrelated cards

## Token Extraction Report

Report:

```text
Scope:
Files scanned:
Top hardcoded colors:
Top inline style files:
Legacy/MUI surfaces:
Token gaps:
Suggested first convergence slice:
```

## When To Add A Token

Add or propose a token only when:

- an existing token does not fit
- the value is used in multiple active surfaces
- the meaning is stable
- the name describes semantic purpose, not current color

Examples:

- good: `--mac-status-warning-bg`
- weak: `--orange-card-bg`

## When Not To Add A Token

Do not add a token for:

- one-off layout experiments
- temporary migration styles
- data-driven dynamic values
- a single icon size
- visual novelty
