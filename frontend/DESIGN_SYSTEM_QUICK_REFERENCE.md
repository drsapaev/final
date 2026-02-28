# Design System Quick Reference

## Setup (Copy-Paste)

```tsx
// main.jsx - App root
import { ThemeProviderWithContext } from '@/theme/ThemeProviderSetup';
import App from './App';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProviderWithContext initialMode="light">
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ThemeProviderWithContext>
  </React.StrictMode>
);
```

---

## Token Quick Access

### Colors

```tsx
import { colorsLight, colorsDark } from '@/theme/tokens';

colorsLight.primary[500]        // #0ea5e9
colorsLight.secondary[500]      // #8b5cf6
colorsLight.success[500]        // #22c55e
colorsLight.danger[500]         // #ef4444
colorsLight.warning[500]        // #f59e0b
colorsLight.info[500]           // #0ea5e9
colorsLight.neutral[900]        // #111827
colorsLight.neutral[0]          // #ffffff

// Medical specialties
colorsLight.cardiology[500]     // #ef4444
colorsLight.dermatology[500]    // #f04438
colorsLight.neurology[500]      // #6b42ff
colorsLight.orthopedics[500]    // #0ea5e9
colorsLight.ophthalmology[500]  // #f59e0b
colorsLight.dentistry[500]      // #a855f7
```

### Spacing

```tsx
import { spacing } from '@/theme/tokens';

spacing[1]   // 0.25rem (4px)
spacing[2]   // 0.5rem (8px)
spacing[3]   // 0.75rem (12px)
spacing[4]   // 1rem (16px)
spacing[6]   // 1.5rem (24px)
spacing[8]   // 2rem (32px)
```

### Typography

```tsx
import { fontSize, fontWeight, lineHeight } from '@/theme/tokens';

fontSize.xs      // 0.75rem (12px)
fontSize.sm      // 0.875rem (14px)
fontSize.base    // 1rem (16px)
fontSize.lg      // 1.125rem (18px)
fontSize.xl      // 1.25rem (20px)
fontSize['2xl']  // 1.5rem (24px)
fontSize['3xl']  // 1.875rem (30px)

fontWeight.normal      // 400
fontWeight.medium      // 500
fontWeight.semibold    // 600
fontWeight.bold        // 700

lineHeight.tight    // 1.25
lineHeight.normal   // 1.5
lineHeight.relaxed  // 1.625
```

### Border Radius

```tsx
import { borderRadius } from '@/theme/tokens';

borderRadius.sm      // 0.25rem (4px)
borderRadius.md      // 0.5rem (8px)
borderRadius.lg      // 0.75rem (12px)
borderRadius.xl      // 1rem (16px)
borderRadius['2xl']  // 1.5rem (24px)
borderRadius.full    // 9999px (circle)
```

### Shadows

```tsx
import { shadows } from '@/theme/tokens';

shadows.sm      // Subtle
shadows.base    // Standard
shadows.md      // Medium
shadows.lg      // Large
shadows.xl      // Extra large
shadows['2xl']  // Maximum
```

### Transitions

```tsx
import { transitions, easing } from '@/theme/tokens';

transitions.fast    // 150ms
transitions.base    // 200ms
transitions.slow    // 300ms
transitions.slower  // 500ms

easing.easeOut      // Smooth exit
easing.easeInOut    // Smooth both ways
easing.easeIn       // Smooth entry
easing.sharp        // Snappy
```

---

## Component Usage Patterns

### Button Variants

```tsx
import Button from '@mui/material/Button';

<Button variant="contained" color="primary">Primary</Button>
<Button variant="outlined" color="primary">Outlined</Button>
<Button variant="text" color="primary">Text</Button>

<Button variant="contained" color="success">Success</Button>
<Button variant="contained" color="error">Error</Button>
<Button variant="contained" color="warning">Warning</Button>

<Button size="small">Small</Button>
<Button size="medium">Medium</Button>
<Button size="large">Large</Button>

<Button disabled>Disabled</Button>
```

### UnifiedButton (With Medical Colors)

```tsx
import { UnifiedButton } from '@/components/examples/UnifiedButton';

<UnifiedButton>Default Primary</UnifiedButton>
<UnifiedButton variant="outlined">Outlined</UnifiedButton>
<UnifiedButton variant="text">Text</UnifiedButton>

<UnifiedButton medical="cardiology">Cardiology</UnifiedButton>
<UnifiedButton medical="dermatology">Dermatology</UnifiedButton>
<UnifiedButton medical="neurology">Neurology</UnifiedButton>
<UnifiedButton medical="orthopedics">Orthopedics</UnifiedButton>
<UnifiedButton medical="dentistry">Dentistry</UnifiedButton>
<UnifiedButton medical="ophthalmology">Ophthalmology</UnifiedButton>

<UnifiedButton loading>Loading...</UnifiedButton>
<UnifiedButton disabled>Disabled</UnifiedButton>
```

### Card Variants

```tsx
import { UnifiedCard } from '@/components/examples/UnifiedCard';

<UnifiedCard variant="elevated" title="Title">Content</UnifiedCard>
<UnifiedCard variant="outlined" title="Title">Content</UnifiedCard>
<UnifiedCard variant="filled" title="Title">Content</UnifiedCard>
<UnifiedCard variant="soft" title="Title">Content</UnifiedCard>
<UnifiedCard variant="glass" title="Title">Content</UnifiedCard>
<UnifiedCard variant="interactive" title="Title">Content</UnifiedCard>
```

### Typography

```tsx
import Typography from '@mui/material/Typography';

<Typography variant="h1">Display Heading</Typography>
<Typography variant="h2">Page Title</Typography>
<Typography variant="h3">Section Title</Typography>
<Typography variant="h4">Card Title</Typography>
<Typography variant="h5">Subsection</Typography>
<Typography variant="h6">Minor Heading</Typography>
<Typography variant="body1">Standard text</Typography>
<Typography variant="body2">Secondary text</Typography>
<Typography variant="caption">Small label</Typography>
<Typography variant="overline">UPPERCASE LABEL</Typography>
```

### TextField

```tsx
import TextField from '@mui/material/TextField';

<TextField variant="outlined" label="Email" />
<TextField variant="outlined" label="Password" type="password" />
<TextField variant="outlined" multiline rows={4} label="Message" />
<TextField variant="outlined" size="small" label="Small" />
<TextField variant="outlined" size="large" label="Large" />
<TextField variant="outlined" error helperText="Error message" />
<TextField variant="outlined" disabled label="Disabled" />
```

### Dialog

```tsx
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';

<Dialog open={open}>
  <DialogTitle>Confirm Action</DialogTitle>
  <DialogContent>Are you sure?</DialogContent>
  <DialogActions>
    <Button onClick={onCancel}>Cancel</Button>
    <Button onClick={onConfirm} variant="contained">Confirm</Button>
  </DialogActions>
</Dialog>
```

### Table

```tsx
import Table from '@mui/material/Table';
import TableHead from '@mui/material/TableHead';
import TableBody from '@mui/material/TableBody';
import TableRow from '@mui/material/TableRow';
import TableCell from '@mui/material/TableCell';

<Table>
  <TableHead>
    <TableRow>
      <TableCell>Header 1</TableCell>
      <TableCell>Header 2</TableCell>
    </TableRow>
  </TableHead>
  <TableBody>
    <TableRow>
      <TableCell>Data 1</TableCell>
      <TableCell>Data 2</TableCell>
    </TableRow>
  </TableBody>
</Table>
```

### Chip

```tsx
import Chip from '@mui/material/Chip';

<Chip label="Active" color="primary" />
<Chip label="Inactive" variant="outlined" />
<Chip label="Success" color="success" />
<Chip label="Error" color="error" />
<Chip label="Deletable" onDelete={() => {}} />
```

---

## sx Prop Patterns

### Basic Layout

```tsx
import { spacing, borderRadius } from '@/theme/tokens';

<Box sx={{
  display: 'flex',
  gap: spacing[4],
  padding: spacing[6],
  borderRadius: borderRadius.lg,
}}>
  Content
</Box>
```

### Theme Colors

```tsx
import { useTheme } from '@mui/material/styles';

<Box sx={{
  backgroundColor: theme.palette.background.paper,
  color: theme.palette.text.primary,
  borderColor: theme.palette.divider,
}}>
  Content
</Box>
```

### Hover Effects

```tsx
<Box sx={{
  padding: spacing[4],
  backgroundColor: theme.palette.background.paper,
  transition: `all ${transitions.base} ${easing.easeInOut}`,
  '&:hover': {
    backgroundColor: theme.palette.action.hover,
    boxShadow: theme.shadows[3],
    transform: 'translateY(-2px)',
  },
}}>
  Hover me
</Box>
```

### Dark Mode Support

```tsx
<Box sx={{
  backgroundColor: theme.palette.mode === 'light' 
    ? colorsLight.neutral[50] 
    : colorsDark.neutral[100],
  color: theme.palette.text.primary,
}}>
  Content
</Box>

// Better: let theme handle it
<Box sx={{
  backgroundColor: theme.palette.background.default,
  color: theme.palette.text.primary,
}}>
  Content
</Box>
```

---

## Styled Components Pattern

```tsx
import { styled } from '@mui/material/styles';
import { transitions, easing } from '@/theme/tokens';

const StyledButton = styled(Button)(({ theme }) => ({
  textTransform: 'none',
  borderRadius: theme.shape.borderRadius,
  transition: `all ${transitions.base} ${easing.easeInOut}`,
  '&:hover': {
    transform: 'translateY(-2px)',
    boxShadow: theme.shadows[4],
  },
  '&:active': {
    transform: 'translateY(0)',
  },
}));

export function MyButton() {
  return <StyledButton variant="contained">Click</StyledButton>;
}
```

---

## Theme Access Hook

```tsx
import { useTheme } from '@mui/material/styles';

export function MyComponent() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  return (
    <Box sx={{
      color: theme.palette.text.primary,
      backgroundColor: isDark 
        ? theme.palette.background.paper
        : theme.palette.background.default,
    }}>
      Current mode: {theme.palette.mode}
    </Box>
  );
}
```

---

## Dark Mode Toggle

```tsx
import { useTheme } from '@/theme/ThemeProviderSetup';

export function ThemeSwitcher() {
  const { mode, toggleTheme, setMode } = useTheme();

  return (
    <Box sx={{ display: 'flex', gap: '8px' }}>
      <Button 
        onClick={() => setMode('light')}
        variant={mode === 'light' ? 'contained' : 'outlined'}
      >
        Light
      </Button>
      <Button 
        onClick={() => setMode('dark')}
        variant={mode === 'dark' ? 'contained' : 'outlined'}
      >
        Dark
      </Button>
      <Button onClick={toggleTheme}>
        Toggle: {mode}
      </Button>
    </Box>
  );
}
```

---

## Common Anti-Patterns (Don't Do This!)

```tsx
// ❌ BAD: Hardcoded colors
<Button sx={{ backgroundColor: '#0ea5e9' }}>Click</Button>

// ✅ GOOD: Use theme
<Button variant="contained" color="primary">Click</Button>

// ❌ BAD: Arbitrary spacing
<Box sx={{ padding: '14px', marginTop: '18px' }}>Content</Box>

// ✅ GOOD: Use spacing scale
<Box sx={{ padding: spacing[3], marginTop: spacing[4] }}>Content</Box>

// ❌ BAD: Mixed border radius
<Box sx={{ borderRadius: '8px' }} />
<Box sx={{ borderRadius: '10px' }} />

// ✅ GOOD: Consistent scale
<Box sx={{ borderRadius: borderRadius.md }} />
<Box sx={{ borderRadius: borderRadius.lg }} />

// ❌ BAD: Inline styles
<div style={{ color: '#000' }}>Text</div>

// ✅ GOOD: Use sx prop
<Box sx={{ color: theme.palette.text.primary }}>Text</Box>

// ❌ BAD: Ignore dark mode
<Box sx={{ backgroundColor: '#ffffff' }}>Content</Box>

// ✅ GOOD: Theme-aware
<Box sx={{ backgroundColor: theme.palette.background.paper }}>Content</Box>
```

---

## File Reference

| File | Location | Purpose |
|------|----------|---------|
| tokens.ts | `/theme/` | All design values |
| muiTheme.ts | `/theme/` | Theme configuration |
| ThemeProviderSetup.tsx | `/theme/` | Provider + hooks |
| UnifiedButton.tsx | `/components/examples/` | Button examples |
| UnifiedCard.tsx | `/components/examples/` | Card examples |
| DESIGN_SYSTEM_INTEGRATION.md | `/frontend/` | Usage guide |
| DESIGN_SYSTEM_ENFORCEMENT.md | `/frontend/` | Rules & patterns |
| DESIGN_SYSTEM_SUMMARY.md | `/frontend/` | Overview |

---

## Troubleshooting

**Q: Button not colored correctly**  
A: Check theme setup in main.jsx. Wrap with `<ThemeProviderWithContext>`

**Q: Dark mode colors not inverting**  
A: Use `theme.palette.*` instead of direct token imports for semantic colors

**Q: Spacing looks off**  
A: Use `spacing[n]` not arbitrary px values. Check spacing scale.

**Q: ESLint failing on colors**  
A: Replace hardcoded colors with `theme.palette.primary.main`

**Q: Component not styled**  
A: Ensure component is wrapped in ThemeProvider at app root

---

## Keyboard Shortcuts

Common imports to remember:

```tsx
import { spacing, borderRadius, fontSize } from '@/theme/tokens';
import { colorsLight, colorsDark } from '@/theme/tokens';
import { useTheme } from '@mui/material/styles';
import { styled } from '@mui/material/styles';
import { UnifiedButton } from '@/components/examples/UnifiedButton';
import { UnifiedCard } from '@/components/examples/UnifiedCard';
```

---

**Print this page or bookmark for quick reference!** 📌
