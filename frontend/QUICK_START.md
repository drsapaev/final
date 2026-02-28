# Quick Start: Enterprise MUI Design System

## 60-Second Setup

```tsx
// 1. Update src/main.tsx
import { ThemeProviderSetup } from './theme/ThemeProvider';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <ThemeProviderSetup initialMode="light">
    <App />
  </ThemeProviderSetup>
);

// 2. Use in component
import { Button } from '@mui/material';

<Button color="cardiology">Click</Button>

// Done! ✅
```

---

## Using Theme in Components

### Via Native MUI Components
```tsx
import { Button, Card, TextField, Chip, Badge } from '@mui/material';

// Automatic theme styling
<Button variant="contained">Themed</Button>

// Medical specialty colors (auto-available via augmentation)
<Button color="cardiology">Cardiology</Button>
<Chip color="dermatology">Dermatology</Chip>
<Badge color="neurology">Neurology</Badge>
```

### Via sx Prop (Custom Styles)
```tsx
import { Box, Typography } from '@mui/material';
import { useTheme } from '@/theme/ThemeProvider';

const theme = useTheme();

<Box sx={{
  // Use theme tokens
  p: 2,  // padding: spacing[2] = 8px
  m: 3,  // margin: spacing[3] = 12px
  gap: 4,  // gap: spacing[4] = 16px
  
  // Reference palette
  backgroundColor: 'primary.main',
  color: 'text.primary',
  
  // Colors work in light + dark automatically
  borderColor: 'divider',
}}>
  <Typography variant="h5">Medical Card</Typography>
</Box>
```

### Via styled() (Complex Styling)
```tsx
import { styled } from '@mui/material/styles';
import { Box } from '@mui/material';
import { useTheme } from '@/theme/ThemeProvider';

const StyledCard = styled(Box)(({ theme }) => ({
  borderRadius: theme.shape.borderRadius,
  padding: theme.spacing(3),
  backgroundColor: theme.palette.background.paper,
  boxShadow: theme.shadows.md,
  transition: `all ${theme.transitions.duration.base}ms ${theme.transitions.easing.easeInOut}`,
  
  '&:hover': {
    boxShadow: theme.shadows.lg,
  },
  
  '&:focus-visible': {
    outline: `2px solid ${theme.palette.primary.main}`,
  },
}));

export function Card() {
  return <StyledCard>Custom styled card</StyledCard>;
}
```

---

## Token Reference

### Spacing (4px base)
```tsx
spacing[0]  // 0px
spacing[1]  // 4px
spacing[2]  // 8px
spacing[3]  // 12px
spacing[4]  // 16px
spacing[5]  // 20px
spacing[6]  // 24px
// ... up to spacing[24] = 96px
```

### Colors
```tsx
theme.palette.primary[50-900]      // Blue
theme.palette.secondary[50-900]    // Purple
theme.palette.success[50-900]      // Green
theme.palette.warning[50-900]      // Amber
theme.palette.error[50-900]        // Red
theme.palette.info[50-900]         // Cyan

// Medical specialties
theme.palette.cardiology.main      // Pink
theme.palette.dermatology.main     // Purple
theme.palette.neurology.main       // Blue
theme.palette.orthopedics.main     // Orange
theme.palette.ophthalmology.main   // Pink
theme.palette.dentistry.main       // Green
```

### Typography
```tsx
// Use variant prop
<Typography variant="h1">Heading 1</Typography>
<Typography variant="h2">Heading 2</Typography>
<Typography variant="body1">Body text</Typography>
<Typography variant="body2">Small body</Typography>
<Typography variant="caption">Tiny text</Typography>

// Or access directly
const theme = useTheme();
theme.typography.h5.fontSize      // 20px
theme.typography.body1.fontWeight // 400
```

### Shadows
```tsx
theme.shadows.none    // none
theme.shadows.sm      // Subtle
theme.shadows.base    // Default
theme.shadows.md      // Hover
theme.shadows.lg      // Elevated
theme.shadows.xl      // High elevation
theme.shadows['2xl']  // Very high
theme.shadows.inner   // Inset
```

### Border Radius
```tsx
theme.shape.borderRadius       // 8px (default)

// Or use specific values
{
  borderRadius: theme.spacing(1),  // sm: 4px
  borderRadius: theme.spacing(1.5),  // md: 6px
}
```

### Transitions
```tsx
theme.transitions.duration.fast       // 150ms
theme.transitions.duration.base       // 200ms
theme.transitions.duration.slow       // 300ms
theme.transitions.duration.slower     // 500ms

theme.transitions.easing.easeOut      // cubic-bezier(...)
theme.transitions.easing.easeInOut    // cubic-bezier(...)
```

---

## Dark Mode

### Toggle Theme
```tsx
import { useTheme } from '@/theme/ThemeProvider';

function ThemeToggle() {
  const { mode, toggleTheme } = useTheme();
  
  return (
    <Button onClick={toggleTheme}>
      Switch to {mode === 'light' ? 'dark' : 'light'} mode
    </Button>
  );
}
```

### Dark Mode Just Works
Colors automatically invert. No manual code needed.

```tsx
// BEFORE (❌ manual light/dark handling)
<Box sx={{
  backgroundColor: mode === 'light' ? '#ffffff' : '#000000',
  color: mode === 'light' ? '#000000' : '#ffffff',
}}>
  
// AFTER (✅ automatic)
<Box sx={{
  backgroundColor: 'background.paper',
  color: 'text.primary',
}}>
  // Automatically correct in light AND dark mode
```

---

## Medical Specialty Colors

All MUI components support medical colors:

```tsx
<Button color="cardiology">Cardiology</Button>
<Button color="dermatology">Dermatology</Button>
<Button color="neurology">Neurology</Button>
<Button color="orthopedics">Orthopedics</Button>
<Button color="ophthalmology">Ophthalmology</Button>
<Button color="dentistry">Dentistry</Button>

// Works on Chip, Badge, Button, etc.
<Chip color="cardiology" label="Dr. Smith" />
```

---

## Common Patterns

### Custom Button with Theme
```tsx
<Button
  variant="contained"
  color="cardiology"
  sx={{
    textTransform: 'none',
    fontSize: theme.typography.button.fontSize,
    padding: `${theme.spacing(2)}px ${theme.spacing(4)}px`,
  }}
>
  Click
</Button>
```

### Card with Hover
```tsx
<Card sx={{
  p: 3,
  borderRadius: 2,
  transition: `all ${theme.transitions.duration.base}ms`,
  cursor: 'pointer',
  
  '&:hover': {
    boxShadow: theme.shadows.lg,
    transform: 'translateY(-4px)',
  },
}}>
  Content
</Card>
```

### Input with Custom Focus
```tsx
<TextField
  fullWidth
  placeholder="Name"
  sx={{
    '& .MuiOutlinedInput-root': {
      borderRadius: 1.5,
      
      '&:focus-within': {
        boxShadow: `0 0 0 4px ${theme.palette.primary.main}20`,
      },
    },
  }}
/>
```

### Data Table
```tsx
<Table>
  <TableHead sx={{ backgroundColor: theme.palette.grey[100] }}>
    <TableRow>
      <TableCell>Patient</TableCell>
      <TableCell>Department</TableCell>
    </TableRow>
  </TableHead>
  <TableBody>
    <TableRow sx={{
      '&:hover': {
        backgroundColor: theme.palette.action.hover,
      },
    }}>
      <TableCell>John Doe</TableCell>
      <TableCell>
        <Chip color="cardiology" label="Cardiology" />
      </TableCell>
    </TableRow>
  </TableBody>
</Table>
```

---

## Anti-Patterns (❌ DON'T)

```tsx
// ❌ Hardcoded colors
<Box sx={{ color: '#1976d2' }}>Wrong</Box>

// ❌ Magic spacing
<Box sx={{ p: 18, m: 7 }}>Wrong</Box>

// ❌ Inline styles
<Box style={{ backgroundColor: 'white' }}>Wrong</Box>

// ❌ CSS modules
import styles from './Button.module.css';  // Wrong

// ❌ Unnecessary wrappers
<UnifiedButton>  {/* Wrong, use <Button> */}
```

## Best Practices (✅ DO)

```tsx
// ✅ Theme tokens
<Box sx={{ color: 'primary.main' }}>Right</Box>

// ✅ Spacing scale (0, 1, 2, 3, 4...)
<Box sx={{ p: 2, m: 3 }}>Right</Box>

// ✅ sx prop
<Box sx={{ backgroundColor: 'background.paper' }}>Right</Box>

// ✅ styled()
const StyledBox = styled(Box)(({ theme }) => ({
  padding: theme.spacing(2),
}));

// ✅ Native MUI components
<Button>Right</Button>
```

---

## File Locations

```
frontend/src/theme/
├── tokens/              ← All design tokens
│   ├── spacing.ts
│   ├── typography.ts
│   ├── colors.ts
│   ├── shape.ts
│   ├── shadows.ts
│   ├── motion.ts
│   └── index.ts
├── theme.ts            ← Main factory (import here)
├── ThemeProvider.tsx   ← Setup component
├── createPalette.ts
├── createTypography.ts
├── componentOverrides.ts
└── augmentation.ts
```

### Import Path
```tsx
import { useTheme } from '@/theme/ThemeProvider';
import { spacing, fontSize, borderRadius } from '@/theme/tokens';
```

---

## Troubleshooting

### "Theme is undefined"
```tsx
// Make sure you wrapped App with ThemeProvider
<ThemeProviderSetup>
  <App />
</ThemeProviderSetup>
```

### "color="cardiology" not recognized"
Make sure `augmentation.ts` is imported in your app:
```tsx
import '@/theme/augmentation';  // Add this
```

### "Colors not inverting in dark mode"
Use theme palette instead of hardcoded colors:
```tsx
// ❌ Won't invert
sx={{ color: '#000000' }}

// ✅ Will invert
sx={{ color: 'text.primary' }}
```

### "Styles not applying"
Check import order - ThemeProvider must wrap component:
```tsx
<ThemeProviderSetup>
  <App />  {/* Components inside get theme */}
</ThemeProviderSetup>

{/* Components outside won't work */}
```

---

## Resources

| Document | Purpose | Read Time |
|----------|---------|-----------|
| **QUICK_START.md** | This file — patterns & reference | 5 min |
| **ARCHITECTURE.md** | Full technical explanation | 30 min |
| **MIGRATION_STRATEGY.md** | How to migrate 600+ components | 15 min |
| **ENTERPRISE_SUMMARY.md** | Executive overview | 10 min |

---

## Next Steps

1. **Now**: Read ARCHITECTURE.md for full understanding
2. **Today**: Migrate your first 2 components
3. **This Week**: Get team trained on patterns
4. **Next Week**: Begin high-volume migration

Happy theming! 🎨

