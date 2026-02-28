# Unified MUI v5 Design System - Integration Guide

## Quick Start (5 minutes)

### 1. Setup ThemeProvider in App.tsx/App.jsx

```tsx
import { ThemeProviderWithContext } from '@/theme/ThemeProviderSetup';
import App from './App';

export default function Root() {
  return (
    <ThemeProviderWithContext initialMode="light">
      <App />
    </ThemeProviderWithContext>
  );
}
```

### 2. Import & Use Components

```tsx
import { UnifiedButton } from '@/components/examples/UnifiedButton';
import { UnifiedCard } from '@/components/examples/UnifiedCard';

export default function MyComponent() {
  return (
    <UnifiedCard variant="outlined" title="Example">
      <UnifiedButton medical="cardiology">Click Me</UnifiedButton>
    </UnifiedCard>
  );
}
```

---

## Architecture

### File Structure
```
frontend/src/
├── theme/
│   ├── tokens.ts              # Single source of truth (colors, spacing, etc)
│   ├── muiTheme.ts            # MUI createTheme() configuration
│   └── ThemeProviderSetup.tsx  # Provider component & hooks
├── components/
│   └── examples/
│       ├── UnifiedButton.tsx   # Button implementation
│       └── UnifiedCard.tsx     # Card implementation
└── ...
```

### Token System

All design decisions come from `tokens.ts`:

```tsx
import { spacing, colorsLight, colorsDark, fontSize } from '@/theme/tokens';

// Use anywhere
const padding = spacing[4];        // '1rem' (16px)
const color = colorsLight.primary[500];  // '#0ea5e9'
const size = fontSize.lg;          // '1.125rem' (18px)
```

### Color System

**Light Mode Colors** (from `colorsLight`)
```tsx
primary, secondary, success, warning, danger, info,
neutral, cardiology, dermatology, neurology, orthopedics, etc.
```

**Dark Mode Colors** (from `colorsDark`)
Automatically inverted for dark mode support.

**Medical Specialties**
- Cardiology (red tones)
- Dermatology (orange tones)
- Neurology (purple tones)
- Orthopedics (blue tones)
- Ophthalmology (yellow tones)
- Dentistry (purple tones)

### Spacing Scale (4px base)

```tsx
spacing[1]  = 0.25rem  (4px)
spacing[2]  = 0.5rem   (8px)
spacing[3]  = 0.75rem  (12px)
spacing[4]  = 1rem     (16px)
spacing[6]  = 1.5rem   (24px)
spacing[8]  = 2rem     (32px)
// ... continues to spacing[24]
```

---

## Component Usage

### UnifiedButton

**Basic Usage**
```tsx
<UnifiedButton>Click me</UnifiedButton>
<UnifiedButton variant="outlined">Outlined</UnifiedButton>
<UnifiedButton variant="text">Text only</UnifiedButton>
```

**Medical Specialties**
```tsx
<UnifiedButton medical="cardiology">Cardiology Action</UnifiedButton>
<UnifiedButton medical="dermatology">Dermatology Action</UnifiedButton>
<UnifiedButton medical="neurology">Neurology Action</UnifiedButton>
```

**States**
```tsx
<UnifiedButton disabled>Disabled</UnifiedButton>
<UnifiedButton loading>Loading...</UnifiedButton>
```

**Sizes**
```tsx
<UnifiedButton size="small">Small</UnifiedButton>
<UnifiedButton size="medium">Medium</UnifiedButton>
<UnifiedButton size="large">Large</UnifiedButton>
```

### UnifiedCard

**Variants**
```tsx
<UnifiedCard variant="elevated">Elevated (shadow)</UnifiedCard>
<UnifiedCard variant="outlined">Outlined (border)</UnifiedCard>
<UnifiedCard variant="filled">Filled (background)</UnifiedCard>
<UnifiedCard variant="soft">Soft (tinted)</UnifiedCard>
<UnifiedCard variant="glass">Glass (blur effect)</UnifiedCard>
<UnifiedCard variant="interactive">Interactive (hover effects)</UnifiedCard>
```

**With Content**
```tsx
<UnifiedCard 
  variant="outlined" 
  title="Patient Record"
  subtitle="John Doe - ID: 12345"
  size="lg"
>
  <Typography>Patient details go here</Typography>
</UnifiedCard>
```

**With Actions**
```tsx
<UnifiedCard 
  actions={
    <>
      <Button>Cancel</Button>
      <Button variant="contained">Save</Button>
    </>
  }
>
  Card content
</UnifiedCard>
```

---

## MUI Component Overrides

All standard MUI components are automatically styled:

- **Button** → Uses primary/secondary colors + medical variants
- **Card/Paper** → Consistent shadows + borders
- **TextField/Input** → Uniform styling + focus states
- **Dialog** → Rounded corners + proper shadows
- **Chip** → Theme-aware colors + hover effects
- **Table** → Consistent cell styling
- **MenuItem** → Proper hover/selected states
- **Badge** → Status colors

**No additional setup needed** - just use MUI components normally:

```tsx
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Card from '@mui/material/Card';

// All automatically styled per theme
<Button variant="contained">Auto-themed!</Button>
<TextField variant="outlined" />
<Card>Auto-themed!</Card>
```

---

## Using sx Prop (MUI styling)

```tsx
import { useTheme } from '@mui/material/styles';
import { spacing, colorsLight } from '@/theme/tokens';

export function MyComponent() {
  const theme = useTheme();
  
  return (
    <Box
      sx={{
        padding: spacing[4],
        backgroundColor: theme.palette.primary.main,
        borderRadius: '12px',
        transition: 'all 200ms cubic-bezier(0.4, 0, 0.6, 1)',
        '&:hover': {
          boxShadow: theme.shadows[4],
        },
      }}
    >
      Content
    </Box>
  );
}
```

---

## Styled Component Pattern

```tsx
import { styled } from '@mui/material/styles';
import { transitions, easing } from '@/theme/tokens';

const StyledBox = styled(Box)(({ theme }) => ({
  padding: theme.spacing(4),
  backgroundColor: theme.palette.background.paper,
  transition: `all ${transitions.base} ${easing.easeInOut}`,
  '&:hover': {
    boxShadow: theme.shadows[2],
  },
}));

export function MyComponent() {
  return <StyledBox>Styled content</StyledBox>;
}
```

---

## Dark Mode Switching

### Option 1: Using Context Hook

```tsx
import { useTheme } from '@/theme/ThemeProviderSetup';

export function ThemeSwitcher() {
  const { mode, toggleTheme } = useTheme();
  
  return (
    <Button onClick={toggleTheme}>
      Current: {mode} | Toggle
    </Button>
  );
}
```

### Option 2: Set Mode Programmatically

```tsx
import { useTheme } from '@/theme/ThemeProviderSetup';

export function ModeSelector() {
  const { setMode } = useTheme();
  
  return (
    <div>
      <Button onClick={() => setMode('light')}>Light</Button>
      <Button onClick={() => setMode('dark')}>Dark</Button>
    </div>
  );
}
```

---

## Typography Scale

```
h1:        3rem    (48px)  - Display headings
h2:        2.25rem (36px)  - Page titles
h3:        1.875rem (30px) - Section headings
h4:        1.5rem   (24px) - Subsection headings
h5:        1.25rem  (20px) - Card titles
h6:        1.125rem (18px) - Minor headings
body1:     1rem     (16px) - Standard body text
body2:     0.875rem (14px) - Secondary text
subtitle1: 1rem     (16px) - Subtitle (bold)
subtitle2: 0.875rem (14px) - Secondary subtitle
caption:   0.75rem  (12px) - Captions/hints
overline:  0.75rem  (12px) - Labels (UPPERCASE)
```

---

## Border Radius Scale

```
none:    '0'           No radius
sm:      '0.25rem'     4px   - Subtle
default: '0.375rem'    6px   - Standard
md:      '0.5rem'      8px   - Default components
lg:      '0.75rem'     12px  - Cards
xl:      '1rem'        16px  - Large components
2xl:     '1.5rem'      24px  - Dialogs
3xl:     '2rem'        32px  - Extra large
full:    '9999px'      Fully rounded
```

---

## Shadow System

```
none:    No shadow
sm:      Subtle (1px elevation)
base:    Standard (hover state)
md:      Medium (card hover)
lg:      Large (modal)
xl:      Extra large (floating menu)
2xl:     Maximum (modals, popovers)
inner:   Inset shadow
```

---

## Transitions & Easing

```tsx
transitions.fast   = '150ms'   - Quick interactions
transitions.base   = '200ms'   - Standard animations
transitions.slow   = '300ms'   - Page transitions
transitions.slower = '500ms'   - Modal appearances

easing.easeOut   = 'cubic-bezier(0.4, 0, 0.2, 1)'
easing.easeInOut = 'cubic-bezier(0.4, 0, 0.6, 1)'
easing.easeIn    = 'cubic-bezier(0.4, 0, 1, 1)'
easing.sharp     = 'cubic-bezier(0.4, 0, 0.6, 1)'
```

---

## Migration Guide

### Before (Bad ❌)
```tsx
// Hardcoded colors
<Button style={{ backgroundColor: '#0ea5e9', padding: '16px' }}>
  Click
</Button>

// Inconsistent spacing
<Box sx={{ marginTop: '20px', paddingLeft: '12px' }}>
  Content
</Box>

// Mixed radii
<Card sx={{ borderRadius: '8px' }}>
  <Box sx={{ borderRadius: '12px' }}>
    Inner
  </Box>
</Card>
```

### After (Good ✅)
```tsx
// Use theme colors
<UnifiedButton>Click</UnifiedButton>

// Use spacing scale
<Box sx={{ marginTop: spacing[5], paddingLeft: spacing[3] }}>
  Content
</Box>

// Consistent radii
<UnifiedCard variant="outlined">
  <Box sx={{ borderRadius: borderRadius.md }}>
    Inner
  </Box>
</UnifiedCard>
```

---

## Best Practices

### ✅ DO

- Use `tokens.ts` for all design values
- Use `sx` prop for dynamic styling
- Use `styled()` for reusable component variants
- Reference `theme.palette` in hooks
- Use MUI component variants
- Implement light + dark mode via `palette.mode`

### ❌ DON'T

- Hardcode colors (e.g., `color: '#0ea5e9'`)
- Use random spacing values (e.g., `padding: '14px'`)
- Mix border radius values
- Create parallel theme systems
- Use inline styles over `sx` prop
- Ignore theme overrides for components

---

## Testing

### Test Light + Dark Mode
```tsx
import { render } from '@testing-library/react';
import { ThemeProviderWithContext } from '@/theme/ThemeProviderSetup';

test('Component works in dark mode', () => {
  render(
    <ThemeProviderWithContext initialMode="dark">
      <MyComponent />
    </ThemeProviderWithContext>
  );
  // assertions...
});
```

### Test Theme Access
```tsx
import { useTheme } from '@mui/material/styles';

test('Component accesses theme correctly', () => {
  const theme = useTheme();
  expect(theme.palette.primary.main).toBe('#0ea5e9');
});
```

---

## FAQ

**Q: Can I override component styles?**  
A: Yes! Use `sx` prop or `styled()` - theme is applied automatically.

**Q: How do I add custom colors?**  
A: Add to `tokens.ts` → `colorsLight/colorsDark`, then update `muiTheme.ts`.

**Q: Can I change brand colors globally?**  
A: Yes! Update `colorsLight.primary[500]` in tokens.ts, one place.

**Q: How do I support a new medical specialty?**  
A: Add to `colorsLight.{specialty}` and `colorsDark.{specialty}` in tokens.ts.

**Q: What if I need custom spacing?**  
A: Use `spacing[n]` scale. If none fit, add to `tokens.ts`.

---

## Support

For questions or issues:
1. Check `tokens.ts` for available design values
2. Review component examples in `/components/examples/`
3. Check MUI docs: https://mui.com/material-ui/
4. Ask team lead about design system decisions
