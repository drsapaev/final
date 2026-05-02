# 🎨 UNIFIED DESIGN SYSTEM v2.0
## Medical System - Premium, Cohesive, Production-Grade

---

## 📋 Table of Contents
1. [Quick Start](#quick-start)
2. [Core Principles](#core-principles)
3. [Color System](#color-system)
4. [Typography](#typography)
5. [Spacing & Layout](#spacing--layout)
6. [Border Radius](#border-radius)
7. [Shadows & Elevation](#shadows--elevation)
8. [Component Usage](#component-usage)
9. [Anti-Patterns (What NOT to Do)](#anti-patterns-what-not-to-do)
10. [Migration Checklist](#migration-checklist)
11. [Code Review Guidelines](#code-review-guidelines)

---

## Quick Start

### 1. Import the Design System
```jsx
// In your component
import { unifiedTheme } from '@/theme/unifiedTheme';

// Usage
const buttonStyles = {
  backgroundColor: unifiedTheme.colors.primary[500],
  padding: `${unifiedTheme.spacing[2]} ${unifiedTheme.spacing[4]}`,
  borderRadius: unifiedTheme.borderRadius.md,
};
```

### 2. Use CSS Variables (Preferred)
```jsx
// In your CSS/styled-component
button {
  background-color: var(--color-primary-500);
  padding: var(--spacing-2) var(--spacing-4);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  transition: all var(--duration-base) var(--easing-smooth);
}
```

### 3. Use Theme Hook (For Dynamic Theming)
```jsx
import { useTheme } from '@/contexts/ThemeContext';
import { unifiedTheme } from '@/theme/unifiedTheme';

export function MyButton() {
  const { isDark } = useTheme();
  const colors = isDark ? unifiedTheme.colors.dark : unifiedTheme.colors.semantic;
  
  return (
    <button style={{ 
      background: colors.text.primary 
    }}>
      Click me
    </button>
  );
}
```

---

## Core Principles

### 1. **Single Source of Truth**
- ✅ All design tokens defined in `/theme/unifiedTheme.js`
- ✅ CSS custom properties in `/styles/unified.css`
- ❌ NO hardcoded colors, spacing, or radii anywhere in components
- ❌ NO separate theme files (`theme.css`, `macos-tokens.css`, etc.)

### 2. **Semantic Over Literal**
- ✅ Use `colors.status.success` instead of `#10b981`
- ✅ Use `colors.medical.cardiology` for specialty colors
- ✅ Use `spacing[4]` for 16px padding
- ❌ NO direct hex values
- ❌ NO arbitrary pixel sizes

### 3. **Consistent Across Modes**
- ✅ Light + Dark mode support built-in
- ✅ Use semantic color keys (auto-switches)
- ❌ NO mode-specific inline styles
- ❌ NO hardcoded backgrounds/text colors

### 4. **Accessible by Default**
- ✅ WCAG AAA contrast ratios (all colors tested)
- ✅ Focus states on all interactive elements
- ✅ Proper semantic HTML
- ❌ NO low-contrast text
- ❌ NO elements without focus indicators

### 5. **Performance First**
- ✅ CSS variables for dynamic theming (no re-renders)
- ✅ System fonts (no custom font requests)
- ✅ Hardware-accelerated transitions
- ❌ NO runtime CSS calculations
- ❌ NO imported Google Fonts

---

## Color System

### Primary Colors (Brand)
```js
// ALWAYS use from theme
colors.primary[50-900]     // Blue scale for primary actions

// Example: Primary button
background: unifiedTheme.colors.primary[500];  // #3b82f6
```

### Status Colors (Semantic)
```js
colors.status.success   // #10b981 - Treatment, completion, approval
colors.status.warning   // #f59e0b - Pending, needs attention
colors.status.danger    // #ef4444 - Emergency, critical
colors.status.info      // #06b6d4 - Information, notes
colors.status.neutral   // #6b7280 - Neutral state
```

### Medical Department Colors
```js
colors.medical.cardiology    // #dc2626 - Red (Cardiology)
colors.medical.dermatology   // #8b5cf6 - Purple (Dermatology)
colors.medical.dentistry     // #059669 - Green (Dentistry)
colors.medical.laboratory    // #0891b2 - Teal (Labs)
colors.medical.neurology     // #a855f7 - Magenta (Neurology)
colors.medical.gynecology    // #ec4899 - Pink (Gynecology)
// ... 6 more specialties

// Usage: Specialty-specific buttons
<ModernButton variant="cardiology">Schedule Cardiology</ModernButton>
```

### Semantic Colors (Dark Mode Safe)
```js
// These auto-swap in dark mode
colors.semantic.text.primary          // #111827 (light) → #f9fafb (dark)
colors.semantic.background.primary    // #ffffff (light) → #0f172a (dark)
colors.semantic.border.light          // #e5e7eb (light) → #475569 (dark)
colors.semantic.surface.card          // #ffffff (light) → #1e293b (dark)

// Usage:
style={{ 
  background: colors.semantic.background.primary,  // Adapts to mode!
  color: colors.semantic.text.primary
}}
```

### Dark Mode Overrides
```js
// In dark mode context:
colors.dark.text.primary            // #f9fafb
colors.dark.background.primary      // #0f172a
colors.dark.border.light            // #475569
colors.dark.surface.card            // #1e293b
```

---

## Typography

### Font Stack
```js
typography.fontFamily.sans     // System fonts (no custom font requests)
typography.fontFamily.mono     // Monospace for code
```

### Type Scale
```js
// Always use these sizes, never arbitrary pixels
typography.fontSize.xs     // 12px - captions, tags
typography.fontSize.sm     // 14px - labels, small text
typography.fontSize.base   // 16px - body text
typography.fontSize.lg     // 18px - body emphasis
typography.fontSize.xl     // 20px - subheadings
typography.fontSize['2xl'] // 24px - section headings
typography.fontSize['3xl'] // 30px - page headings
typography.fontSize['4xl'] // 36px - major headings
typography.fontSize['5xl'] // 48px - display text
```

### Font Weights
```js
typography.fontWeight.normal      // 400 - body
typography.fontWeight.medium      // 500 - labels, emphasis
typography.fontWeight.semibold    // 600 - subheadings
typography.fontWeight.bold        // 700 - headings
typography.fontWeight.extrabold   // 800 - display
```

### Line Heights
```js
typography.lineHeight.tight    // 1.25 - headings
typography.lineHeight.normal   // 1.5 - body (MOST COMMON)
typography.lineHeight.relaxed  // 1.75 - lists, emphasized
typography.lineHeight.loose    // 2 - minimal text
```

### Preset Styles
```js
// Use these ready-made combinations
typography.styles.h1   // 36px, 700, 1.2
typography.styles.h2   // 30px, 600, 1.3
typography.styles.body // 16px, 400, 1.5
typography.styles.bodySmall // 14px, 400, 1.5
typography.styles.label // 14px, 500, 1.4
typography.styles.caption // 12px, 400, 1.4
```

### Usage Examples
```jsx
// ✅ GOOD - Using preset styles
<h1 style={unifiedTheme.typography.styles.h1}>
  Welcome to Medical System
</h1>

// ✅ GOOD - Using individual tokens
<p style={{
  fontSize: unifiedTheme.typography.fontSize.sm,
  fontWeight: unifiedTheme.typography.fontWeight.medium,
  lineHeight: unifiedTheme.typography.lineHeight.normal,
  color: unifiedTheme.colors.semantic.text.secondary
}}>
  Secondary text
</p>

// ❌ BAD - Hardcoded values
<h1 style={{ fontSize: '36px', fontWeight: 700 }}>Wrong!</h1>

// ❌ BAD - Arbitrary size
<p style={{ fontSize: '15px' }}>Also wrong!</p>
```

---

## Spacing & Layout

### Spacing Scale (4px base)
```js
spacing[0]   // 0px
spacing[1]   // 4px    ← minimum
spacing[2]   // 8px    ← small gap
spacing[3]   // 12px
spacing[4]   // 16px   ← standard
spacing[6]   // 24px   ← comfortable
spacing[8]   // 32px   ← generous
spacing[10]  // 40px
spacing[12]  // 48px   ← large sections
spacing[16]  // 64px
spacing[20]  // 80px   ← xl spacing
```

### Common Patterns
```jsx
// Button padding: 10px 16px = spacing[2] + spacing[4]
<button style={{ 
  padding: `${spacing[2]} ${spacing[4]}` 
}}>
  Standard Button
</button>

// Card padding: always spacing[6] (24px)
<div style={{ 
  padding: spacing[6] 
}}>
  Card content
</div>

// Spacing between items: spacing[4] (16px)
<div style={{ 
  display: 'flex',
  flexDirection: 'column',
  gap: spacing[4]
}}>
  {items.map(...)}
</div>
```

### DO NOT
```jsx
// ❌ NO arbitrary spacing
padding: '10px 18px'
margin: '24px'
gap: '14px'

// ✅ YES - Use scale
padding: `${spacing[2]} ${spacing[5]}`
margin: spacing[6]
gap: spacing[4]
```

---

## Border Radius

### Radius Scale (Consistent)
```js
borderRadius.none      // 0px - no border
borderRadius.sm        // 4px - small elements
borderRadius.base      // 6px - DEFAULT for small components ★
borderRadius.md        // 8px - DEFAULT for medium components ★
borderRadius.lg        // 12px - cards, larger elements
borderRadius.xl        // 16px - modals, dialog boxes
borderRadius['2xl']    // 20px - special emphasis
borderRadius['3xl']    // 24px - largest containers
borderRadius.full      // 9999px - fully rounded (circles, pills)
```

### Usage by Component
```js
// Buttons: always .md (8px)
<button style={{ borderRadius: borderRadius.md }}>

// Input fields: always .md (8px)
<input style={{ borderRadius: borderRadius.md }} />

// Cards: always .lg (12px)
<div style={{ borderRadius: borderRadius.lg }}>

// Modals/Dialogs: always .xl (16px)
<dialog style={{ borderRadius: borderRadius.xl }}>

// Pills/Badges: always .full
<span style={{ borderRadius: borderRadius.full }}>
```

### DO NOT
```jsx
// ❌ NO arbitrary radius
borderRadius: '10px'
borderRadius: '15px'
borderRadius: '18px'

// ✅ YES
borderRadius: borderRadius.md
borderRadius: borderRadius.lg
borderRadius: borderRadius.full
```

---

## Shadows & Elevation

### Shadow Scale (Soft Modern)
```js
shadows.none        // No shadow (flat)
shadows.xs          // Subtle (hover states)
shadows.sm          // Light (cards, small elevation)
shadows.base        // Standard (default cards)
shadows.md          // Medium (interactive hover)
shadows.lg          // Large (floating elements)
shadows.xl          // Extra large (modal overlay)
shadows['2xl']      // Maximum (special emphasis)
shadows.inner       // Inset (depth effect)
```

### Usage Patterns
```jsx
// Cards (at rest): use .sm or .base
<div style={{ boxShadow: shadows.sm }}>
  Card content
</div>

// Cards (hover): upgrade to .md
card:hover {
  box-shadow: shadows.md;
  transform: translateY(-2px);
}

// Floating buttons: use .lg
<div style={{ boxShadow: shadows.lg }}>
  Floating action
</div>

// Modal backdrop: use .2xl
<div style={{ boxShadow: shadows['2xl'] }}>
  Modal content
</div>
```

### Dark Mode Shadows
Shadows are AUTOMATICALLY stronger in dark mode (built into CSS variables).
No manual override needed!

---

## Transitions & Motion

### Duration (Always use these)
```js
transitions.duration.fast      // 100ms - quick feedback
transitions.duration.base      // 150ms - DEFAULT ★
transitions.duration.slow      // 200ms - noticeable change
transitions.duration.slower    // 300ms - emphasis
transitions.duration.slowest   // 500ms - special effects
```

### Easing (Choose the right curve)
```js
transitions.easing.in          // Accelerating (cubic-bezier(0.4, 0, 1, 1))
transitions.easing.out         // Decelerating (cubic-bezier(0, 0, 0.2, 1))
transitions.easing.inOut       // Smooth both ways (DEFAULT) ★
transitions.easing.linear      // Consistent speed
transitions.easing.smooth      // Design system favorite
```

### Usage
```jsx
// ✅ Button hover
button {
  transition: all var(--duration-base) var(--easing-smooth);
}

button:hover {
  background-color: colors.primary[600];
  transform: translateY(-1px);
}

// ✅ Color change
div {
  transition: color var(--duration-slow) var(--easing-out);
}

// ❌ AVOID slow animations (unless intentional)
transition: all 1s ease;  // Too slow!
```

---

## Component Usage

### Buttons
```jsx
import ModernButton from '@/components/buttons/ModernButton';

// ✅ GOOD - Uses design system variants
<ModernButton 
  variant="primary"
  size="medium"
  disabled={isLoading}
  loading={isLoading}
>
  Submit Form
</ModernButton>

// Medical specialty buttons
<ModernButton variant="cardiology">Cardiology</ModernButton>
<ModernButton variant="dentistry">Dentistry</ModernButton>

// ❌ BAD - Custom inline styles
<button style={{ 
  backgroundColor: '#3b82f6',
  padding: '10px 16px',
  borderRadius: '8px'
}}>
  Wrong approach
</button>
```

### Cards
```jsx
// ✅ GOOD - Semantic structure
<article style={{
  background: colors.semantic.surface.card,
  border: `1px solid ${colors.semantic.border.light}`,
  borderRadius: borderRadius.lg,
  padding: spacing[6],
  boxShadow: shadows.sm,
}}>
  <h2>Card Title</h2>
  <p>Card content</p>
</article>

// ❌ BAD - Wrong shadow/radius
<div style={{
  background: '#fff',
  borderRadius: '15px',
  boxShadow: '0 5px 10px rgba(0,0,0,0.15)',
}}>
```

### Forms
```jsx
// ✅ GOOD - Consistent input styling
<input 
  style={{
    fontSize: typography.fontSize.base,
    padding: `${spacing[2]} ${spacing[3]}`,
    border: `1px solid ${colors.semantic.border.light}`,
    borderRadius: borderRadius.md,
    color: colors.semantic.text.primary,
  }}
  placeholder="Enter text..."
/>

// ✅ Focus state handled automatically via CSS
input:focus {
  border-color: var(--color-border-focus);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}
```

### Status Badges
```jsx
// ✅ GOOD - Semantic status colors
function StatusBadge({ status }) {
  const statusColor = {
    success: colors.status.success,
    warning: colors.status.warning,
    danger: colors.status.danger,
  }[status];

  return (
    <span style={{
      background: statusColor,
      color: colors.semantic.text.inverse,
      padding: `${spacing[1]} ${spacing[3]}`,
      borderRadius: borderRadius.full,
      fontSize: typography.fontSize.xs,
      fontWeight: typography.fontWeight.semibold,
    }}>
      {status.toUpperCase()}
    </span>
  );
}
```

---

## Anti-Patterns (What NOT to Do)

### 🔴 Pattern 1: Hardcoded Colors
```jsx
// ❌ NEVER DO THIS
<button style={{ backgroundColor: '#3b82f6' }}>
  Button
</button>

// ✅ ALWAYS DO THIS
<button style={{ backgroundColor: unifiedTheme.colors.primary[500] }}>
  Button
</button>
```

### 🔴 Pattern 2: Arbitrary Spacing
```jsx
// ❌ NO magic numbers
<div style={{ padding: '14px', margin: '9px', gap: '18px' }}>

// ✅ USE THE SCALE
<div style={{ 
  padding: spacing[3],     // 12px
  margin: spacing[2],      // 8px
  gap: spacing[4]          // 16px
}}>
```

### 🔴 Pattern 3: Inconsistent Border Radius
```jsx
// ❌ Different radii everywhere
borderRadius: '8px'
borderRadius: '10px'
borderRadius: '15px'
borderRadius: '20px'

// ✅ STANDARDIZED SCALE
borderRadius: borderRadius.md      // 8px for buttons
borderRadius: borderRadius.lg       // 12px for cards
borderRadius: borderRadius.xl       // 16px for modals
```

### 🔴 Pattern 4: Multiple Shadow Systems
```jsx
// ❌ Hardcoded shadows all over
boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
boxShadow: '0 5px 10px rgba(0,0,0,0.15)'
boxShadow: 'custom shadow string'

// ✅ UNIFIED SCALE
boxShadow: shadows.sm
boxShadow: shadows.md
boxShadow: shadows.lg
```

### 🔴 Pattern 5: Ignoring Dark Mode
```jsx
// ❌ Hardcoded colors (breaks in dark mode)
<div style={{ 
  background: '#ffffff',
  color: '#111827'
}}>

// ✅ SEMANTIC (auto-adapts to mode)
<div style={{ 
  background: colors.semantic.background.primary,
  color: colors.semantic.text.primary
}}>
```

### 🔴 Pattern 6: Inconsistent Button Variants
```jsx
// ❌ Custom button styles scattered
<button style={{ background: '#10b981' }}>Success</button>
<button style={{ background: '#ef4444' }}>Danger</button>

// ✅ USE ModernButton VARIANTS
<ModernButton variant="success">Success</ModernButton>
<ModernButton variant="danger">Danger</ModernButton>
```

### 🔴 Pattern 7: Too Many Font Sizes
```jsx
// ❌ Custom sizes
fontSize: '13px'
fontSize: '15px'
fontSize: '17px'
fontSize: '19px'

// ✅ USE SCALE
fontSize: typography.fontSize.sm      // 14px
fontSize: typography.fontSize.base    // 16px
fontSize: typography.fontSize.lg      // 18px
fontSize: typography.fontSize.xl      // 20px
```

### 🔴 Pattern 8: Slow/Inconsistent Transitions
```jsx
// ❌ Random durations/easing
transition: 'all 0.5s ease'
transition: 'color 300ms cubic-bezier(...)'
transition: 'all 1s ease-in-out'

// ✅ STANDARDIZED
transition: `all ${transitions.duration.base} ${transitions.easing.smooth}`
transition: `background-color ${transitions.duration.slow} ${transitions.easing.out}`
```

### 🔴 Pattern 9: !important Overrides
```jsx
// ❌ Using !important (indicates design system failure)
background-color: #fff !important;
color: red !important;

// ✅ CASCADE PROPERLY
// Use correct specificity instead
```

### 🔴 Pattern 10: Mixing Theming Systems
```jsx
// ❌ Using old theme files alongside new one
import from '/styles/theme.css'         // ❌ OLD
import from '/theme/macos-tokens.css'   // ❌ OLD
import from '/design-system/styles/global.css'  // ❌ OLD

// ✅ USE ONLY THE UNIFIED SYSTEM
import { unifiedTheme } from '/theme/unifiedTheme.js'
import '/styles/unified.css'
```

---

## Migration Checklist

### Phase 1: Foundation (Week 1)
- [ ] Import `/styles/unified.css` in main app entry
- [ ] Import `unifiedTheme` in component files
- [ ] Update `App.jsx` to use unified theme provider
- [ ] Delete old theme files:
  - [ ] `/styles/theme.css`
  - [ ] `/theme/macos-tokens.css`
  - [ ] `/design-system/styles/global.css`
  - [ ] Any other competing theme files

### Phase 2: Component Migration (Week 2-3)
**Start with highest-impact components:**
1. [ ] `ModernButton.jsx` - Replace inline styles with theme
2. [ ] `ModernCard.jsx` - Update shadows and spacing
3. [ ] Form components (Input, Select, Textarea)
4. [ ] Navigation components
5. [ ] Modal/Dialog components

**For each component:**
- [ ] Replace hardcoded colors → `colors.*.{value}`
- [ ] Replace spacing → `spacing[n]`
- [ ] Replace borderRadius → `borderRadius.*`
- [ ] Replace shadows → `shadows.*`
- [ ] Test in both light and dark modes

### Phase 3: Cleanup (Week 4)
- [ ] Remove all inline color definitions
- [ ] Remove all arbitrary spacing values
- [ ] Remove all custom borderRadius values
- [ ] Audit CSS files for !important
- [ ] Add design system linter rules (ESLint)

### Phase 4: Enforcement (Ongoing)
- [ ] Add pre-commit hook (husky)
- [ ] Run design system validator
- [ ] Code review checklist
- [ ] Monitor for regressions

---

## Code Review Guidelines

### Checklist for Every PR

#### Colors
- [ ] Are hardcoded colors used? (Reject: Use `colors.*`)
- [ ] Are colors semantic or arbitrary hex? (Must be semantic)
- [ ] Does it work in dark mode? (Test both modes)
- [ ] Is contrast >= WCAG AA? (Use contrast checker)

#### Spacing
- [ ] Does spacing follow the 4px scale? (No: 9px, 14px, 18px, etc.)
- [ ] Is spacing consistent? (Similar components = similar spacing)
- [ ] Are margins + padding balanced? (Not mixing margin/gap)

#### Typography
- [ ] Are font sizes from the scale? (Only .xs, .sm, .base, .lg, .xl, .2xl, .3xl, .4xl, .5xl)
- [ ] Are font weights correct? (400, 500, 600, 700, 800 only)
- [ ] Is line-height readable? (Use preset styles when possible)

#### Border Radius
- [ ] Are border radii consistent? (sm, base, md, lg, xl, 2xl, 3xl, full only)
- [ ] Do buttons use .md? (All buttons should be 8px)
- [ ] Do cards use .lg? (All cards should be 12px)
- [ ] Do modals use .xl? (All dialogs should be 16px)

#### Shadows
- [ ] Are shadows from the scale? (Not custom box-shadow values)
- [ ] Is shadow elevation appropriate? (Light cards .sm, hover .md, modals .lg)
- [ ] Do shadows look good in dark mode? (Auto-handled, but verify)

#### Transitions
- [ ] Are durations standardized? (Only 100ms, 150ms, 200ms, 300ms, 500ms)
- [ ] Is easing consistent? (Prefer `easing-smooth`)
- [ ] Respect prefers-reduced-motion? (Auto-handled by CSS)

#### Accessibility
- [ ] Do interactive elements have focus states? (outline or box-shadow)
- [ ] Is text readable on backgrounds? (Contrast >= 4.5:1)
- [ ] Are semantic HTML elements used? (button, input, nav, etc.)
- [ ] Are ARIA labels present where needed? (For screen readers)

---

## Migration Examples

### Example 1: Button Component
```jsx
// BEFORE (Inconsistent, hardcoded)
const ModernButton = ({ variant = 'primary', ...props }) => {
  const colors = {
    primary: { bg: '#3b82f6', text: '#fff', hover: '#2563eb' },
    danger: { bg: '#ef4444', text: '#fff', hover: '#dc2626' },
  };
  
  const buttonStyles = {
    padding: '10px 16px',  // ❌ Hardcoded
    borderRadius: '8px',   // ❌ Hardcoded
    fontSize: '14px',      // ❌ Hardcoded
    fontWeight: '500',     // ❌ Hardcoded
    transition: 'all 0.2s ease',  // ❌ Hardcoded
  };
  
  return <button style={buttonStyles} {...props} />;
};

// AFTER (Unified theme)
import { unifiedTheme } from '@/theme/unifiedTheme';
const { colors, spacing, borderRadius, typography, transitions } = unifiedTheme;

const ModernButton = ({ variant = 'primary', ...props }) => {
  const variantColors = {
    primary: colors.primary,
    danger: colors.status.danger,
  };
  
  const buttonStyles = {
    padding: `${spacing[2]} ${spacing[4]}`,  // ✅ 8px 16px from scale
    borderRadius: borderRadius.md,           // ✅ 8px from scale
    fontSize: typography.fontSize.base,      // ✅ 16px from scale
    fontWeight: typography.fontWeight.medium, // ✅ 500 from scale
    transition: `all ${transitions.duration.base} ${transitions.easing.smooth}`,  // ✅ 150ms
    backgroundColor: variantColors[variant][500],
  };
  
  return <button style={buttonStyles} {...props} />;
};
```

### Example 2: Card Component
```jsx
// BEFORE (Multiple shadow systems)
const Card = ({ children }) => {
  return (
    <div style={{
      background: '#fff',
      border: '1px solid #e5e7eb',
      borderRadius: '12px',
      padding: '24px',
      boxShadow: '0 4px 6px rgba(0,0,0,0.1)',  // ❌ Custom
    }}>
      {children}
    </div>
  );
};

// AFTER (Unified)
import { unifiedTheme } from '@/theme/unifiedTheme';
const { colors, spacing, borderRadius, shadows } = unifiedTheme;

const Card = ({ children }) => {
  return (
    <div style={{
      background: colors.semantic.surface.card,        // ✅ Auto dark mode
      border: `1px solid ${colors.semantic.border.light}`,  // ✅ Auto dark mode
      borderRadius: borderRadius.lg,                   // ✅ 12px
      padding: spacing[6],                            // ✅ 24px
      boxShadow: shadows.sm,                          // ✅ Unified
    }}>
      {children}
    </div>
  );
};
```

---

## Enforcement & Tools

### ESLint Rules (Recommended)
```js
// .eslintrc.json additions
{
  "rules": {
    "no-hardcoded-colors": "error",  // Prevent #fff, #000, etc.
    "no-arbitrary-spacing": "error", // Prevent padding/margin not from scale
    "no-custom-border-radius": "error",  // Prevent arbitrary borderRadius
  }
}
```

### Pre-commit Hook (Husky)
```bash
#!/bin/sh
# .husky/pre-commit

npm run lint:design-system
npm run test:design-system
```

### Design System Validator
```js
// scripts/validate-design-system.js
// Check every component for violations
```

---

## Troubleshooting

### Issue: Dark mode colors not applying
```jsx
// ✅ SOLUTION: Use semantic colors
background: colors.semantic.background.primary,  // Auto-adapts
// ❌ DON'T: Hardcode colors
background: '#ffffff',
```

### Issue: Spacing is uneven
```jsx
// ✅ SOLUTION: Use spacing scale consistently
padding: spacing[4],
margin: spacing[2],
gap: spacing[3],

// ❌ DON'T: Mix scales
padding: '16px',
margin: '8px',
gap: '12px',
```

### Issue: Buttons look inconsistent
```jsx
// ✅ SOLUTION: Use ModernButton with variants
<ModernButton variant="primary">Primary</ModernButton>

// ❌ DON'T: Custom button styles
<button style={{ background: '#3b82f6' }}>
```

---

## Quick Reference Cards

### Colors
| Use | Token | Value |
|-----|-------|-------|
| Primary button | `colors.primary[500]` | #3b82f6 |
| Success status | `colors.status.success` | #10b981 |
| Danger status | `colors.status.danger` | #ef4444 |
| Cardiology dept | `colors.medical.cardiology` | #dc2626 |
| Text primary | `colors.semantic.text.primary` | #111827 |
| Border light | `colors.semantic.border.light` | #e5e7eb |

### Spacing
| Use | Token | Value |
|-----|-------|-------|
| Minimal gap | `spacing[1]` | 4px |
| Small gap | `spacing[2]` | 8px |
| Standard | `spacing[4]` | 16px |
| Comfortable | `spacing[6]` | 24px |
| Generous | `spacing[8]` | 32px |

### Border Radius
| Use | Token | Value |
|-----|-------|-------|
| Buttons | `borderRadius.md` | 8px |
| Cards | `borderRadius.lg` | 12px |
| Modals | `borderRadius.xl` | 16px |
| Pills | `borderRadius.full` | 9999px |

### Shadows
| Use | Token |
|-----|-------|
| Cards (rest) | `shadows.sm` |
| Cards (hover) | `shadows.md` |
| Floating | `shadows.lg` |
| Modals | `shadows.xl` |

---

**Last Updated:** February 28, 2026  
**Version:** 2.0 - Unified  
**Maintainers:** Design Systems Team
