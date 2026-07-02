# Design System Enforcement Guide

## ESLint Rules (Prevent Anti-Patterns)

### Install eslint-plugin-mui-design

```bash
npm install --save-dev eslint-plugin-material-ui-design
```

### ESLint Configuration (.eslintrc.json)

```json
{
  "extends": ["react-app"],
  "plugins": ["material-ui-design"],
  "rules": {
    "material-ui-design/no-hardcoded-colors": "error",
    "material-ui-design/prefer-theme-palette": "error",
    "material-ui-design/prefer-spacing-scale": "warn",
    "material-ui-design/no-arbitrary-border-radius": "warn"
  }
}
```

### Custom ESLint Rules

Create `.eslintrc.custom.js`:

```javascript
module.exports = {
  rules: {
    'no-hardcoded-colors': {
      create(context) {
        return {
          Literal(node) {
            const value = node.value;
            if (typeof value === 'string' && /^#[0-9a-f]{6}$/i.test(value)) {
              context.report({
                node,
                message: `Hardcoded color '${value}' detected. Use theme.palette or tokens instead.`,
                fix(fixer) {
                  return fixer.replaceText(node, 'theme.palette.primary.main');
                }
              });
            }
          }
        };
      }
    },
    'no-arbitrary-padding': {
      create(context) {
        return {
          CallExpression(node) {
            if (node.callee.property?.name === 'sx') {
              const props = node.arguments[0]?.properties || [];
              props.forEach(prop => {
                if (/padding|margin/.test(prop.key.name)) {
                  const value = prop.value.value;
                  if (typeof value === 'string' && /^\d+px$/.test(value)) {
                    context.report({
                      node: prop.value,
                      message: `Use spacing scale instead of arbitrary '${value}'`,
                      fix(fixer) {
                        return fixer.replaceText(prop.value, 'spacing[n]');
                      }
                    });
                  }
                }
              });
            }
          }
        };
      }
    }
  }
};
```

---

## Pre-Commit Hooks (Husky)

### Setup Husky

```bash
npm install husky --save-dev
npx husky install
npx husky add .husky/pre-commit "npm run lint"
```

### Pre-commit Script (.husky/pre-commit)

```bash
#!/bin/sh
. "$(dirname "$0")/_/husky.sh"

echo "🎨 Running design system compliance checks..."

# Check for hardcoded colors
if grep -r "#[0-9a-f]\{6\}" frontend/src/components --include="*.tsx" --include="*.jsx" | grep -v "node_modules" | grep -v ".test"; then
  echo "❌ Hardcoded colors detected! Use theme.palette instead."
  exit 1
fi

# Check for arbitrary padding
if grep -r "padding: '[0-9]*px'" frontend/src/components --include="*.tsx" --include="*.jsx" | grep -v "node_modules"; then
  echo "❌ Arbitrary padding detected! Use spacing scale instead."
  exit 1
fi

# Run ESLint
npm run lint

if [ $? -ne 0 ]; then
  echo "❌ ESLint check failed!"
  exit 1
fi

echo "✅ Design system checks passed!"
```

---

## Code Review Checklist

### Before Merging PR

- [ ] **No hardcoded colors** - All colors from `theme.palette` or tokens
- [ ] **Consistent spacing** - Only `spacing[n]` from tokens used
- [ ] **Unified border radius** - Only `borderRadius.*` scale used
- [ ] **Theme-aware shadows** - Uses `theme.shadows[n]` or token shadows
- [ ] **Proper typography** - Uses theme typography variants
- [ ] **Light + Dark mode** - Component tested in both modes
- [ ] **No inline styles** - Uses `sx` prop or `styled()` instead
- [ ] **Accessibility** - Proper ARIA labels, focus states, contrast
- [ ] **Component consistency** - Follows existing patterns
- [ ] **No CSS imports** - Unless necessary for third-party styles

### Example Code Review Template

```markdown
## Design System Review

### Color Usage ✅/❌
- [ ] All colors from theme.palette
- [ ] Medical colors used appropriately
- [ ] Contrast WCAG AA/AAA compliant

### Spacing ✅/❌
- [ ] Uses spacing[n] scale
- [ ] Consistent gaps between elements
- [ ] Proper visual hierarchy

### Typography ✅/❌
- [ ] Uses theme typography variants
- [ ] Correct font weights applied
- [ ] Readable line heights

### Components ✅/❌
- [ ] Uses UnifiedButton/UnifiedCard
- [ ] Consistent with existing patterns
- [ ] Proper variant selection

### Dark Mode ✅/❌
- [ ] Tested in dark mode
- [ ] Colors automatically adjust
- [ ] No hardcoded colors for light-only

### Accessibility ✅/❌
- [ ] Focus states visible
- [ ] ARIA labels present
- [ ] Keyboard navigation works
```

---

## Common Anti-Patterns & Fixes

### 1. Hardcoded Colors

❌ **BAD**
```tsx
<Button sx={{ backgroundColor: '#0ea5e9' }}>
  Click
</Button>
```

✅ **GOOD**
```tsx
<Button variant="contained" color="primary">
  Click
</Button>

// Or with sx:
<Button sx={{ backgroundColor: theme.palette.primary.main }}>
  Click
</Button>
```

---

### 2. Arbitrary Spacing

❌ **BAD**
```tsx
<Box sx={{ padding: '14px', marginTop: '18px', gap: '9px' }}>
  Content
</Box>
```

✅ **GOOD**
```tsx
import { spacing } from '@/theme/tokens';

<Box sx={{ 
  padding: spacing[3],      // 12px
  marginTop: spacing[4],    // 16px
  gap: spacing[2],          // 8px
}}>
  Content
</Box>
```

---

### 3. Inconsistent Border Radius

❌ **BAD**
```tsx
<Card sx={{ borderRadius: '8px' }}>
  <Paper sx={{ borderRadius: '10px' }}>
    <Box sx={{ borderRadius: '12px' }} />
  </Paper>
</Card>
```

✅ **GOOD**
```tsx
import { borderRadius } from '@/theme/tokens';

<Card sx={{ borderRadius: borderRadius.lg }}>
  <Paper sx={{ borderRadius: borderRadius.lg }}>
    <Box sx={{ borderRadius: borderRadius.md }} />
  </Paper>
</Card>
```

---

### 4. Multiple Theme Systems

❌ **BAD**
```tsx
// theme-old.css
.btn-primary { background: #0ea5e9; }

// component.tsx
import './theme-old.css';
<button className="btn-primary">Click</button>
```

✅ **GOOD**
```tsx
import { UnifiedButton } from '@/components/examples/UnifiedButton';

<UnifiedButton variant="contained">Click</UnifiedButton>
```

---

### 5. Ignoring Theme Palette

❌ **BAD**
```tsx
const colors = {
  primary: '#0ea5e9',
  secondary: '#8b5cf6',
  danger: '#ef4444'
};

export function MyButton() {
  return <button style={{ color: colors.primary }} />;
}
```

✅ **GOOD**
```tsx
import { useTheme } from '@mui/material/styles';

export function MyButton() {
  const theme = useTheme();
  return <button style={{ color: theme.palette.primary.main }} />;
}
```

---

### 6. No Dark Mode Support

❌ **BAD**
```tsx
<Box sx={{ 
  backgroundColor: '#ffffff',
  color: '#000000'
}}>
  Content
</Box>
```

✅ **GOOD**
```tsx
<Box sx={{ 
  backgroundColor: theme.palette.background.paper,
  color: theme.palette.text.primary
}}>
  Content
</Box>
```

---

### 7. Direct CSS Overrides

❌ **BAD**
```tsx
import './my-styles.css'; // Creates CSS specificity wars

<Button className="my-button">Click</Button>
```

✅ **GOOD**
```tsx
import { styled } from '@mui/material/styles';

const MyButton = styled(Button)(({ theme }) => ({
  backgroundColor: theme.palette.primary.main,
  '&:hover': {
    backgroundColor: theme.palette.primary.dark,
  }
}));

<MyButton>Click</MyButton>
```

---

### 8. Inconsistent Shadows

❌ **BAD**
```tsx
<Box sx={{
  boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
  '&:hover': {
    boxShadow: '0 4px 8px rgba(0,0,0,0.15)'
  }
}}>
  Content
</Box>
```

✅ **GOOD**
```tsx
import { shadows } from '@/theme/tokens';
import { useTheme } from '@mui/material/styles';

<Box sx={{
  boxShadow: shadows.sm,
  '&:hover': {
    boxShadow: shadows.md
  }
}}>
  Content
</Box>

// Or use theme.shadows
<Box sx={{
  boxShadow: theme.shadows[1],
  '&:hover': {
    boxShadow: theme.shadows[3]
  }
}}>
  Content
</Box>
```

---

### 9. Hard-coded Font Sizes

❌ **BAD**
```tsx
<Typography sx={{ fontSize: '14px', fontWeight: 600 }}>
  Heading
</Typography>
```

✅ **GOOD**
```tsx
import { fontSize, fontWeight } from '@/theme/tokens';

<Typography 
  variant="h6"
  sx={{ fontSize: fontSize.lg, fontWeight: fontWeight.semibold }}
>
  Heading
</Typography>

// Or simpler:
<Typography variant="h6">Heading</Typography>
```

---

### 10. Ignoring Medical Colors

❌ **BAD**
```tsx
<Button sx={{ backgroundColor: '#ef4444' }}>
  Cardiology Action
</Button>
```

✅ **GOOD**
```tsx
import { UnifiedButton } from '@/components/examples/UnifiedButton';

<UnifiedButton medical="cardiology">Cardiology Action</UnifiedButton>
```

---

## Automated Code Fixes

### Run ESLint --fix

```bash
npm run lint -- --fix
```

### Search & Replace with Regex

#### Replace hardcoded colors
```
Find:    backgroundColor: '[#a-f0-9]{6}|rgb\([\d,\s]+\)'
Replace: backgroundColor: theme.palette.primary.main
```

#### Replace arbitrary padding
```
Find:    padding: '[0-9]{1,3}px'
Replace: padding: spacing[4]
```

#### Replace inline border-radius
```
Find:    borderRadius: '[0-9]{1,3}px'
Replace: borderRadius: borderRadius.lg
```

---

## Team Guidelines

### Design System Decisions

1. **All color changes** → Update `tokens.ts` → `colorsLight/colorsDark`
2. **New spacing value** → Add to `tokens.ts` spacing scale
3. **New component variant** → Create in `/components/examples/`
4. **Typography change** → Update `muiTheme.ts` typography config
5. **Shadow adjustment** → Update `tokens.ts` shadows object

### Pull Request Template

```markdown
## Design System Compliance

### Changes Made
- [ ] Updated tokens.ts
- [ ] Updated muiTheme.ts
- [ ] Created example component
- [ ] Tested light mode
- [ ] Tested dark mode

### Color Review
- Used theme.palette: YES / NO
- New colors added to tokens: YES / NO / N/A

### Spacing Review
- All values from spacing scale: YES / NO
- No arbitrary px values: YES / NO

### Testing
- [ ] ESLint passes
- [ ] Dark mode works
- [ ] All components render
- [ ] Accessibility checked
```

---

## Ongoing Maintenance

### Monthly Design Audit

```bash
# Check for hardcoded colors
grep -r "#[0-9a-f]\{6\}" frontend/src --include="*.tsx" --include="*.jsx"

# Check for arbitrary spacing
grep -r "padding: '" frontend/src --include="*.tsx"
grep -r "margin: '" frontend/src --include="*.tsx"

# Count CSS files (should be minimal)
find frontend/src -name "*.css" | wc -l

# Report findings to team
```

### Quarterly Review

- [ ] Are all colors from theme.palette?
- [ ] Is spacing consistent with scale?
- [ ] Are border radii unified?
- [ ] Is dark mode fully supported?
- [ ] Are medical colors being used?
- [ ] Are legacy styles still present?
- [ ] Do we need new tokens?

---

## Training

### Developer Onboarding

1. Read `DESIGN_SYSTEM_INTEGRATION.md`
2. Review `tokens.ts` - understand available values
3. Try modifying example components
4. Implement one small feature using design system
5. Complete code review checklist

### Design System Workshop (1 hour)

- [ ] Token system overview (10 min)
- [ ] Using theme in components (15 min)
- [ ] Dark mode support (10 min)
- [ ] Medical colors & semantic meaning (10 min)
- [ ] Q&A (15 min)

---

## Success Metrics

✅ **Design System Adoption**
- 95%+ of new code uses theme/tokens
- <5% hardcoded colors in codebase
- 100% dark mode support
- All components follow patterns

✅ **Code Quality**
- ESLint passes consistently
- Pre-commit hooks prevent violations
- Code reviews enforce standards
- Zero CSS specificity wars

✅ **Developer Experience**
- New developers productive in <2 hours
- Style changes take <5 minutes
- Theme switching is seamless
- Medical colors are intuitive

---

## Contact & Questions

- **Design System Owner**: [Name]
- **Slack Channel**: #design-system
- **Documentation**: `/frontend/DESIGN_SYSTEM_*.md`
- **Tokens**: `/frontend/src/theme/tokens.ts`
