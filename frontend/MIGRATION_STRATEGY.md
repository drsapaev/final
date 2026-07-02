# Migration Strategy: 600+ Components to Unified Theme

## Quick Links
- **Setup Time**: 5 minutes
- **Learning Curve**: <2 hours
- **Migration Timeline**: 4 weeks
- **Team Size**: 2-3 developers (parallel)
- **Risk Level**: LOW (can run alongside existing code)

---

## Phase Overview

```
Week 1: Foundation Setup
├─ Deploy theme system (done)
├─ Update App.tsx to use ThemeProvider
├─ Test 5 sample components manually
└─ Success: App loads, theme switching works

Week 2-3: High-Priority Migration
├─ Buttons (20 components) — Day 1
├─ Cards (15 components) — Day 2
├─ Forms (25 components) — Days 3-4
└─ Success: 60 components migrated, no visual regressions

Week 4: Remaining + Enforcement
├─ Data Display (40 components)
├─ Feedback (15 components)
├─ Navigation (20 components)
└─ Success: 100% coverage, ESLint enabled, CI passing
```

---

## PHASE 1: Foundation (Days 1-2)

### 1.1 Update App Entry Point

**File: `src/main.tsx`**

```tsx
// BEFORE
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// AFTER
import App from './App';
import { ThemeProviderSetup } from './theme/ThemeProvider';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProviderSetup initialMode="light">
      <App />
    </ThemeProviderSetup>
  </React.StrictMode>
);
```

### 1.2 Verify Theme Loading

**File: `src/App.tsx`** (add test component)

```tsx
import { useTheme } from './theme/ThemeProvider';
import { Button, Box, Typography } from '@mui/material';

export function App() {
  const { mode, toggleTheme } = useTheme();

  return (
    <Box sx={{ p: 4 }}>
      <Typography variant="h1">Design System Test</Typography>
      <Typography variant="body1">Current mode: {mode}</Typography>
      <Button variant="contained" onClick={toggleTheme}>
        Toggle Theme
      </Button>
      <Button color="cardiology" variant="outlined">
        Cardiology
      </Button>
    </Box>
  );
}
```

### 1.3 Test Manually

```bash
# Start dev server
npm run dev

# Check:
# ✅ Page loads (theme applied)
# ✅ Colors correct in light mode
# ✅ Toggle button switches to dark mode
# ✅ Colors correct in dark mode
# ✅ Cardiology button is pink (medical color)
```

### 1.4 Success Criteria

- [ ] App loads without errors
- [ ] Light mode displays correctly
- [ ] Dark mode toggle works
- [ ] Medical colors display
- [ ] No console warnings

---

## PHASE 2A: Button Migration (Day 3)

### Before Pattern (❌ CHAOTIC)

```tsx
// Component 1: Using styled-components with hardcoded colors
const StyledButton = styled(Button)`
  background-color: #0ea5e9;
  color: white;
  padding: 8px 16px;
  border-radius: 6px;
  &:hover {
    background-color: #0284c7;
  }
`;

// Component 2: Using sx prop with hardcoded colors
function MyButton() {
  return (
    <Button sx={{ 
      backgroundColor: '#0ea5e9',
      color: 'white',
      padding: '8px 16px'
    }}>
      Click
    </Button>
  );
}

// Component 3: Using inline styles
function OtherButton() {
  return (
    <Button style={{
      backgroundColor: 'rgb(14, 165, 233)',
      padding: '8px 16px'
    }}>
      Click
    </Button>
  );
}
```

### After Pattern (✅ UNIFIED)

```tsx
import { Button } from '@mui/material';
import { useTheme } from '@/theme/ThemeProvider';

// Now use native MUI with theme tokens
function MyButton() {
  const theme = useTheme();
  
  return (
    <Button variant="contained">
      Click
    </Button>
  );
}

// For medical specialty colors:
function CardiacButton() {
  return (
    <Button color="cardiology" variant="contained">
      Cardiology
    </Button>
  );
}

// For customization:
function CustomButton() {
  return (
    <Button sx={{
      backgroundColor: 'primary.main',  // ✅ Token reference
      '&:hover': {
        backgroundColor: 'primary.dark',
      },
    }}>
      Custom
    </Button>
  );
}
```

### Step-by-Step Migration for Each Button

1. **Find all button usages**
   ```bash
   grep -r "Button\|button\|styled.*Button" src/components --include="*.tsx"
   ```

2. **For each file with buttons:**

   ```tsx
   // BEFORE: Hardcoded + styled component
   const PrimaryButton = styled(Button)`
     background: #0ea5e9;
     padding: 8px 16px;
     border-radius: 6px;
   `;

   // AFTER: Remove styled component, use theme directly
   function PrimaryButton(props) {
     return <Button variant="contained" {...props} />;
   }
   ```

3. **Verify in browser:**
   - Light mode looks identical
   - Dark mode shows inverted colors (automatic)
   - Hover states work

4. **Commit:**
   ```bash
   git add src/components/buttons/
   git commit -m "refactor: migrate Button to unified theme"
   ```

### Files to Migrate (Example)
- src/components/buttons/PrimaryButton.tsx
- src/components/buttons/SecondaryButton.tsx
- src/components/buttons/DangerButton.tsx
- src/components/buttons/CardiacButton.tsx
- ... (20 total)

**Estimated Time**: 1 day for 1 developer

---

## PHASE 2B: Card Migration (Day 4)

### Before (❌)

```tsx
const StyledCard = styled(Card)`
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  padding: 16px;
  background-color: white;
  
  &:hover {
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  }
`;

function PatientCard({ name }) {
  return (
    <StyledCard>
      <Typography sx={{ fontSize: '16px', fontWeight: 700 }}>
        {name}
      </Typography>
    </StyledCard>
  );
}
```

### After (✅)

```tsx
function PatientCard({ name }) {
  return (
    <Card>
      <Typography variant="h6">
        {name}
      </Typography>
    </Card>
  );
}
```

Why this works:
- Card styling → theme.ts (componentOverrides)
- Typography → already in theme.ts
- No wrapper component needed

**Estimated Time**: 1 day for 1 developer

---

## PHASE 2C: Form Migration (Days 5-6)

### TextField Pattern

```tsx
// BEFORE: Hardcoded colors
<TextField
  sx={{
    '& .MuiOutlinedInput-root': {
      borderRadius: '8px',
      backgroundColor: '#ffffff',
      '& fieldset': {
        borderColor: '#e0e0e0',
      },
      '&:hover fieldset': {
        borderColor: '#0ea5e9',
      },
    },
  }}
/>

// AFTER: Theme-managed
<TextField
  variant="outlined"
  // All styling via theme.ts
/>
```

For custom variants:
```tsx
<TextField
  sx={{
    '& .MuiOutlinedInput-root': {
      borderRadius: 'md',  // Use borderRadius token
    },
  }}
/>
```

**Estimated Time**: 1.5 days for 1 developer

---

## PHASE 3: Bulk Automation (Days 7-10)

### ESLint Enforcement ON

**File: `.eslintrc.json`**

```json
{
  "extends": ["...", ".eslintrc.theme.js"],
  "overrides": [
    {
      "files": ["src/components/**/*.tsx"],
      "rules": {
        "no-hardcoded-colors": "error"
      }
    }
  ]
}
```

Run:
```bash
npx eslint src/components --fix

# Output:
# 237 errors found
# 156 automatically fixed
# 81 require manual review
```

### Manual Fixes for Remaining 81

Use this script to find them:

```bash
grep -r "#[0-9a-f]\{6\}\|rgb(" src/components --include="*.tsx" \
  | head -20
```

### Automated Codemod (Optional)

```bash
# Install codemod CLI
npm install --global codemod

# Run color replacer
codemod --source src/components \
  --pattern "#0ea5e9" \
  --replacement "theme.palette.primary.main"
```

**Estimated Time**: 2 days for 1 developer (automated + manual fixes)

---

## Risk Mitigation

### Risk 1: Breaking Changes

**Mitigation:**
- Keep old theme system for 1 week (parallel)
- Gradual migration component-by-component
- Full test coverage before merging

### Risk 2: Visual Regressions

**Mitigation:**
- Screenshot every component before/after
- Visual regression testing with Chromatic
- Manual QA on dark mode

### Risk 3: Team Misunderstanding

**Mitigation:**
- 1-hour team walkthrough of ARCHITECTURE.md
- Code review checklist for PRs
- Pair programming for first few migrations

---

## Success Metrics

By Week 4, measure:

| Metric | Target | Result |
|--------|--------|--------|
| Components migrated | 100% | __% |
| Hardcoded colors | 0 | __% |
| ESLint pass rate | 100% | __% |
| Dark mode working | 100% | __% |
| Build time | <2min | __ms |
| Bundle size | <2KB gzipped | __KB |
| Team velocity | stable | ✓/✗ |

---

## Week-by-Week Checklist

### Week 1
- [ ] Theme deployed
- [ ] ThemeProvider in App.tsx
- [ ] Light/dark toggle works
- [ ] 5 components tested manually
- [ ] No console errors

### Week 2
- [ ] All Buttons migrated (20 files)
- [ ] All Cards migrated (15 files)
- [ ] No visual regressions
- [ ] Dark mode verified
- [ ] Team trained

### Week 3
- [ ] All Forms migrated (25 files)
- [ ] Layout components done (30 files)
- [ ] ESLint warnings <50
- [ ] Build passing
- [ ] PR code review checklist used

### Week 4
- [ ] Data Display migrated (40 files)
- [ ] Feedback components done (15 files)
- [ ] ESLint errors 0
- [ ] CI/CD enforcement on
- [ ] Storybook updated
- [ ] Team documentation complete

---

## After Migration: Preventing Chaos

### Enforce via CI

```yaml
name: Design System Lint
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: npm install
      - run: npx eslint src --config .eslintrc.theme.js --max-warnings 0
```

### Pre-Commit Hook

```bash
# husky pre-commit
npx eslint src --cache
```

### Code Review Checklist

```markdown
## Design System Review

- [ ] No hardcoded colors (#fff, rgb(...))
- [ ] Spacing uses 4px scale
- [ ] Border radius from theme.shape
- [ ] Shadows from theme.shadows
- [ ] Typography from theme
- [ ] Dark mode tested
- [ ] Accessibility: focus states visible
- [ ] No inline <style> tags
- [ ] No CSS modules
```

---

## FAQ

**Q: Will components break during migration?**  
A: No. Migrated components use exact same styling. Only visual change is dark mode now works automatically.

**Q: What about legacy browser support?**  
A: MUI handles it. Theme system is CSS-in-JS, fully transpiled.

**Q: Do we need to remove old CSS files?**  
A: Yes. Once component is migrated, delete old .css/.scss files.

**Q: What about CSS modules?**  
A: Phase them out gradually. Use `sx` prop instead.

**Q: Can we keep makeStyles for complex components?**  
A: Yes, but migrate over time. Use `sx` for new code.

**Q: How to handle component props still using colors?**  
A: Add prop validation:
```tsx
type ButtonColor = 'primary' | 'secondary' | 'cardiology' | ...;
interface MyButtonProps {
  color?: ButtonColor;
}
```

---

## Team Communication Template

```markdown
## Design System Migration: Week 1 Complete ✅

All theme system deployed. Starting component migration this week.

### What Changed
- All colors now in single `theme.ts`
- Dark mode automatic via theme switching
- Medical specialty colors available: `color="cardiology"` etc.

### For Developers
1. Use native MUI components (no wrappers)
2. Reference theme for custom styles: `sx={{ color: 'primary.main' }}`
3. Use ESLint to catch violations

### Next Steps
- Buttons migration: Days 1-2
- Cards migration: Days 3-4
- All others: Days 5+

Questions? Check ARCHITECTURE.md or ask in #design-system
```

---

This migration path is designed to be zero-impact on production, parallelizable across the team, and low-risk at every step.
