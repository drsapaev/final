# Unified MUI v5 Design System - Master Index

**Status:** ✅ Production Ready  
**Version:** 1.0.0  
**Date:** February 28, 2026

---

## 📋 Documentation Map

### 🚀 Start Here (Choose Your Path)

| I want to... | Read this | Time |
|--------------|-----------|------|
| **Get started NOW** | [QUICK_REFERENCE.md](#quick-reference) | 5 min |
| **Understand the system** | [DESIGN_SYSTEM_SUMMARY.md](#summary) | 15 min |
| **Learn how to use it** | [DESIGN_SYSTEM_INTEGRATION.md](#integration) | 20 min |
| **Enforce consistency** | [DESIGN_SYSTEM_ENFORCEMENT.md](#enforcement) | 15 min |

---

## 📚 Complete Documentation

### **QUICK_REFERENCE.md** {#quick-reference}
**Fast lookup for developers**

- Copy-paste setup code
- Token quick access (colors, spacing, typography)
- Component usage patterns
- sx prop examples
- Styled component patterns
- Dark mode toggle code
- Common anti-patterns
- Troubleshooting

**Best for:** Developers needing quick answers  
**Read:** When you need specific syntax  

---

### **DESIGN_SYSTEM_SUMMARY.md** {#summary}
**Complete overview and implementation guide**

- Executive summary
- What you get (files, components, docs)
- Architecture overview
- Color system (light/dark mode)
- Spacing, typography, border radius scales
- Shadow system
- Transition timings
- Component overrides (built-in)
- Implementation phases (Week-by-week)
- Migration checklist
- Success criteria
- Team responsibilities

**Best for:** Understanding the full system  
**Read:** First time setup, stakeholder review  

---

### **DESIGN_SYSTEM_INTEGRATION.md** {#integration}
**Detailed usage and implementation guide**

- Quick start (5 minutes)
- Architecture overview
- Token system explanation
- Color system deep dive
- Spacing scale guide
- Typography scale reference
- Border radius reference
- Shadow system reference
- Transition & easing reference
- Component usage (Button, Card, TextField, Dialog, Table, etc.)
- Using sx prop
- Styled component patterns
- Dark mode switching (3 methods)
- Migration guide (before/after)
- Best practices (DO/DON'T)
- Testing patterns
- FAQ

**Best for:** Learning how to use the system  
**Read:** When implementing components  

---

### **DESIGN_SYSTEM_ENFORCEMENT.md** {#enforcement}
**Rules, patterns, and code review standards**

- ESLint rules setup
- Custom ESLint rules for design tokens
- Pre-commit hooks with Husky
- Code review checklist
- 10 common anti-patterns with fixes
- Automated code fixes
- Team guidelines
- Pull request template
- Monthly design audit scripts
- Quarterly review checklist
- Developer onboarding
- Training workshop outline
- Success metrics

**Best for:** Maintaining consistency  
**Read:** Before code review, setting up enforcement  

---

## 🗂️ Core Files Location

### Theme System (`/frontend/src/theme/`)

```
tokens.ts                    ← Single source of truth (colors, spacing, typography)
muiTheme.ts                  ← MUI createTheme() implementation
ThemeProviderSetup.tsx       ← Provider component + theme hooks
```

### Example Components (`/frontend/src/components/examples/`)

```
UnifiedButton.tsx            ← Button with medical specialties
UnifiedCard.tsx              ← Card with 6 variants
```

---

## ⚡ Setup Checklist

### Immediate (Today)
- [ ] Copy theme files to `/frontend/src/theme/`
- [ ] Copy component examples to `/frontend/src/components/examples/`
- [ ] Update `main.jsx` with ThemeProvider
- [ ] Test light + dark mode rendering

### This Week
- [ ] Run `npm install` (dependencies auto-installed)
- [ ] Review QUICK_REFERENCE.md
- [ ] Update first high-priority component
- [ ] Test in browser
- [ ] Team reviews system

### This Month
- [ ] Migrate buttons, cards, dialogs (Week 1)
- [ ] Setup ESLint + pre-commit hooks (Week 1)
- [ ] Migrate forms (Week 2)
- [ ] Migrate tables/lists (Week 3)
- [ ] Final polish + audit (Week 4)

---

## 🎯 Quick Navigation by Role

### 👨‍💻 Developers
1. Read [QUICK_REFERENCE.md](#quick-reference) (5 min)
2. Read [DESIGN_SYSTEM_INTEGRATION.md](#integration) sections 1-3 (10 min)
3. Try modifying an example component (10 min)
4. Implement your first component (30 min)

**Key files:**
- `/frontend/src/theme/tokens.ts` - Reference all tokens
- `/components/examples/UnifiedButton.tsx` - Copy patterns
- `/components/examples/UnifiedCard.tsx` - Copy patterns

### 🎨 Designers
1. Read [DESIGN_SYSTEM_SUMMARY.md](#summary) - Color System section
2. Review color palettes in `tokens.ts`
3. Review component variants in example files
4. Provide feedback on medical colors

**Key sections:**
- Color System (light/dark modes)
- Medical Specialty Colors
- Component Examples

### 👔 Leads & PMs
1. Read [DESIGN_SYSTEM_SUMMARY.md](#summary) - Executive Summary
2. Read Implementation Phases section
3. Review Migration Checklist
4. Review Team Responsibilities section

**Key metrics:**
- Setup time: 5 minutes
- Learning curve: < 2 hours
- Refactoring: 4 weeks (phased)

### 👁️ QA & Code Reviewers
1. Read [DESIGN_SYSTEM_ENFORCEMENT.md](#enforcement) - Code Review Checklist
2. Keep checklist handy during reviews
3. Run automated checks (ESLint, pre-commit)
4. Verify light + dark modes

**Key tool:**
- Code Review Checklist in ENFORCEMENT.md
- QUICK_REFERENCE.md for pattern examples

---

## 🔑 Key Concepts

### Single Source of Truth
All design decisions come from `tokens.ts`:
- No scattered CSS files
- No hardcoded colors
- No competing theme systems
- Easy to maintain for 3+ years

### 4px Spacing Base
```
1 unit = 4px
spacing[1] = 4px
spacing[2] = 8px
spacing[4] = 16px
spacing[6] = 24px
```

### Semantic Colors
```
primary, secondary, success, warning, danger, info
+ Medical specialties: cardiology, dermatology, neurology, etc.
```

### Light + Dark Mode
Colors automatically invert. No additional work needed.

### Component Consistency
All MUI components automatically follow the theme. No setup per component needed.

---

## 📊 Token Quick Facts

| Category | Count | Examples |
|----------|-------|----------|
| Colors | 60+ | Primary (9 shades), Medical (6×9) |
| Spacing | 20 | 4px–96px grid |
| Typography | 9 sizes | 12px–48px |
| Border Radius | 8 | sm, md, lg, xl, 2xl, 3xl, full |
| Shadows | 8 | sm, base, md, lg, xl, 2xl, inner |
| Transitions | 4 | 150ms–500ms |

---

## 🚀 File Usage Examples

### Using Tokens

```tsx
import { spacing, colorsLight, fontSize, borderRadius } from '@/theme/tokens';

<Box sx={{
  padding: spacing[4],
  backgroundColor: colorsLight.primary[50],
  fontSize: fontSize.lg,
  borderRadius: borderRadius.lg,
}}>
  Content
</Box>
```

### Using Theme in Components

```tsx
import { useTheme } from '@mui/material/styles';

export function MyComponent() {
  const theme = useTheme();
  return <Button sx={{ color: theme.palette.primary.main }}>Click</Button>;
}
```

### Using Medical Colors

```tsx
import { UnifiedButton } from '@/components/examples/UnifiedButton';

<UnifiedButton medical="cardiology">Cardiology</UnifiedButton>
<UnifiedButton medical="dermatology">Dermatology</UnifiedButton>
```

### Using Dark Mode

```tsx
import { useTheme } from '@/theme/ThemeProviderSetup';

export function ThemeSwitcher() {
  const { toggleTheme } = useTheme();
  return <Button onClick={toggleTheme}>Toggle Dark Mode</Button>;
}
```

---

## ✅ Success Indicators

### Week 1
- [ ] Theme setup complete
- [ ] First component migrated
- [ ] ESLint rules enabled
- [ ] Team trained on basics

### Week 2-3
- [ ] 50+ components migrated
- [ ] Pre-commit hooks working
- [ ] Code reviews using checklist
- [ ] Dark mode fully tested

### Week 4
- [ ] 95%+ code uses tokens
- [ ] Zero hardcoded colors
- [ ] Design audit passed
- [ ] Team confident with system

### Ongoing
- [ ] Monthly audits run
- [ ] Quarterly reviews scheduled
- [ ] New developers onboarded in <2 hours
- [ ] System evolves with team feedback

---

## 🆘 Troubleshooting

### "Theme not applying"
**Solution:** Check ThemeProvider wraps your app in `main.jsx`

### "Dark mode colors look wrong"
**Solution:** Use `theme.palette.*` not direct token imports for semantic colors

### "ESLint complaining about colors"
**Solution:** Replace hardcoded colors with `theme.palette.primary.main`

### "Spacing feels inconsistent"
**Solution:** Use only `spacing[n]` values, never arbitrary px

### "Component styles conflict"
**Solution:** Remove CSS modules/CSS imports, use only MUI theming

See [DESIGN_SYSTEM_INTEGRATION.md FAQ](#integration) for more.

---

## 📞 Getting Help

### Common Questions
→ Read [QUICK_REFERENCE.md](#quick-reference)

### How to Use a Component
→ See example in `/components/examples/`

### Design System Philosophy
→ Read [DESIGN_SYSTEM_SUMMARY.md](#summary)

### Preventing Anti-Patterns
→ Read [DESIGN_SYSTEM_ENFORCEMENT.md](#enforcement)

### Team Onboarding
→ See "Team Responsibilities" section in SUMMARY.md

---

## 📄 All Files at a Glance

### Documentation (4 files)
| File | Purpose | Lines |
|------|---------|-------|
| DESIGN_SYSTEM_INDEX.md | This file - navigation | 400+ |
| DESIGN_SYSTEM_QUICK_REFERENCE.md | Quick lookup | 512 |
| DESIGN_SYSTEM_SUMMARY.md | Complete overview | 565 |
| DESIGN_SYSTEM_INTEGRATION.md | Usage guide | 471 |
| DESIGN_SYSTEM_ENFORCEMENT.md | Rules & patterns | 580 |
| **TOTAL DOCS** | Complete resource | **2,528 lines** |

### Code Files (3 files)
| File | Purpose | Lines |
|------|---------|-------|
| tokens.ts | Design tokens | 498 |
| muiTheme.ts | Theme config | 659 |
| ThemeProviderSetup.tsx | Provider & hooks | 89 |

### Examples (2 files)
| File | Purpose | Lines |
|------|---------|-------|
| UnifiedButton.tsx | Button patterns | 123 |
| UnifiedCard.tsx | Card patterns | 272 |

---

## 🎓 Learning Path

```
START
  ↓
Read QUICK_REFERENCE (5 min)
  ↓
Copy theme files to project (2 min)
  ↓
Setup ThemeProvider in main.jsx (3 min)
  ↓
Read DESIGN_SYSTEM_INTEGRATION sections 1-3 (15 min)
  ↓
Modify one example component (15 min)
  ↓
Implement your first feature using system (30 min)
  ↓
Review code against ENFORCEMENT checklist (5 min)
  ↓
EXPERT LEVEL ✅
```

**Total time to productivity: < 2 hours**

---

## 🏆 What Makes This System Special

✅ **Single Source of Truth**  
All tokens in one file. One theme configuration.

✅ **Zero Hardcoded Colors**  
No `#0ea5e9` scattered everywhere. All from theme.

✅ **100% Dark Mode**  
Colors automatically invert. No manual work.

✅ **Medical Ready**  
6 medical specialty colors built-in.

✅ **Scalable**  
Works for 5–10+ developers without conflicts.

✅ **Maintainable**  
3+ year design changes = minimal code updates.

✅ **Production Ready**  
Complete, tested, documented, exemplified.

✅ **Developer Friendly**  
<2 hour learning curve, consistent patterns.

---

## 🎯 Next Steps

### Right Now
1. Choose your path above (Developer/Designer/Lead)
2. Click the relevant documentation link
3. Start reading!

### Today
1. Copy theme files to project
2. Setup ThemeProvider
3. Test light + dark mode

### This Week
1. Migrate first component
2. Setup ESLint + pre-commit
3. Team training

### This Month
1. Complete phased migration
2. Run design audit
3. Celebrate consistency! 🎉

---

## 📌 Bookmark These

**For Daily Use:**
- [QUICK_REFERENCE.md](#quick-reference) - Syntax lookup

**For Implementation:**
- [DESIGN_SYSTEM_INTEGRATION.md](#integration) - How-to guide

**For Enforcement:**
- [DESIGN_SYSTEM_ENFORCEMENT.md](#enforcement) - Code review

**For Overview:**
- [DESIGN_SYSTEM_SUMMARY.md](#summary) - Big picture

---

**Questions? Check the relevant documentation file above.** 📚

**Ready to build beautiful, consistent medical software?** Let's go! 🚀

---

**Version 1.0.0 | February 28, 2026 | Production Ready ✅**
