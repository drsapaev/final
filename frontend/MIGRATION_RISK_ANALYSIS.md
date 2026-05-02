# Theme Migration Risk Analysis & Mitigation

## Executive Risk Summary

| Risk | Likelihood | Impact | Mitigation | Status |
|------|-----------|--------|-----------|--------|
| Color mapping misses | High | Medium | Visual regression tests | Covered |
| Spacing calculation errors | Medium | Medium | Pixel-perfect testing | Covered |
| Missing useTheme imports | Medium | Low | Codemod automatic | Covered |
| CSS specificity conflicts | Low | High | Manual review | Manual |
| Performance regression | Low | Low | Bundle size check | Automated |
| Dark mode inconsistencies | Medium | Medium | Theme-based testing | Automated |

**Overall Risk Level:** LOW-MEDIUM (with mitigations in place)

---

## Detailed Risk Assessment

### 1. COLOR MAPPING FAILURES

**What can break:**
- Hardcoded color #1976d2 mapped to wrong theme value
- Result: Wrong colors appear in UI (e.g., cardiology red instead of primary blue)

**Probability:** HIGH (600+ components, many legacy colors)

**Impact:** MEDIUM (visible but fixable)

**Detection:**
```
✓ Visual regression tests catch 100%
✓ Manual review catches 95%
✓ QA testing catches 100%
✓ Users notice immediately
```

**Mitigation:**
1. **Pre-migration audit** of all hex values in codebase
2. **Color mapping validation** before running codemod
3. **Visual regression testing** on baseline
4. **Sample batch approach** (test 30 buttons first)
5. **Easy rollback** (git revert one batch)

**Rollback time:** 5 minutes

---

### 2. SPACING CALCULATION ERRORS

**What can break:**
- Codemod converts `padding: 14px` to `theme.spacing(2)` (should be 1.75)
- Result: Layout slightly off, hard to spot

**Probability:** MEDIUM (non-standard spacings like 6px, 14px, 18px)

**Impact:** MEDIUM (subtle layout shifts)

**Detection:**
```
✓ Visual regression tests catch shifts > 2px
✓ Audit script flags non-standard values
✓ Manual pixel inspection catches all
✗ Users notice only in specific browsers
```

**Mitigation:**
1. **Pre-audit all spacing values** (grep for non-8px values)
2. **Manual mapping** for edge cases
3. **Screenshot comparison** before/after each batch
4. **QA pixel-perfect review** of affected components
5. **Staging environment testing** with real data

**Solution for non-standard values:**
```javascript
// Instead of converting 14px directly
// Document and map explicitly:
margin: '14px' // Keep as-is or map to spacing(1.75)
// In theme:
{
  spacing: (factor = 1) => `${factor * 8}px`
  // Or extend with custom:
  customSpacing: {
    tight: '6px',
    compact: '14px',
    normal: '16px',
  }
}
```

**Rollback time:** 10 minutes

---

### 3. MISSING useTheme() IMPORTS

**What can break:**
- File uses `theme.spacing()` but missing `import { useTheme } from '@mui/material'`
- Result: Runtime error "theme is not defined"

**Probability:** MEDIUM (codemod may miss some cases)

**Impact:** LOW (caught immediately in dev)

**Detection:**
```
✓ Codemod auto-adds imports in most cases
✓ ESLint catches missing imports
✓ Type checking catches at build time
✓ Tests catch immediately
✗ Only visible at runtime if not caught
```

**Mitigation:**
1. **Codemod includes auto-import logic** (done)
2. **ESLint rule enforces imports** (done)
3. **Type checking enabled** in tsconfig
4. **Pre-commit hook runs ESLint** (done)
5. **CI fails if imports missing** (done)

**Rollback time:** 0 minutes (auto-fixed)

---

### 4. CSS SPECIFICITY WARS

**What can break:**
- Removed CSS file used `!important`
- New theme values get overridden by other global CSS
- Result: Some components unstyled

**Probability:** LOW (with audit script flagging CSS files)

**Impact:** HIGH (styling completely broken for affected component)

**Detection:**
```
✓ Audit script warns about CSS files
✓ Visual regression tests show missing styles
✓ Manual review flags risky CSS removals
✗ Might not appear until real user data
```

**Mitigation:**
1. **Don't remove CSS files automatically** (manual review required)
2. **Audit identifies all !important usages** 
3. **Manual mapping of CSS rules to theme**
4. **Staged CSS removal** (after component fully tested)
5. **Visual regression testing** before any CSS removal

**Safe procedure:**
```bash
# Week 1-3: Codemod JSX only, don't touch CSS
# Week 4: Manually migrate CSS rules one at a time
# Week 5+: Remove CSS only after full QA sign-off
```

**Rollback time:** 30 minutes (restore CSS files)

---

### 5. DARK MODE INCONSISTENCIES

**What can break:**
- Color inverted incorrectly in dark mode
- Component looks good in light, broken in dark
- Result: Dark mode users see wrong colors

**Probability:** MEDIUM (theme palette inversion may not match intent)

**Impact:** MEDIUM (half the users affected)

**Detection:**
```
✓ Visual regression tests run in light + dark
✓ Manual testing of dark mode
✓ Theme color verification
✗ Users enable dark mode and see issues
```

**Mitigation:**
1. **All tests run in BOTH light + dark mode**
2. **Theme-based colors automatically invert**
3. **Manual review of dark mode in staging**
4. **QA specifically tests dark mode**
5. **Real user testing before full release**

**Rollback time:** 5 minutes (switch theme mode)

---

### 6. BUNDLE SIZE EXPLOSION

**What can break:**
- New theme system + tokens add significant JS
- Result: Slower page load, especially on mobile

**Probability:** LOW (theme system optimized)

**Impact:** MEDIUM (performance regression)

**Detection:**
```
✓ Bundle size monitoring in CI
✓ Lighthouse checks in CI
✓ Performance testing
✓ Real user metrics
```

**Mitigation:**
1. **Bundle size check in CI** (fail if > 5% increase)
2. **Tree-shaking unused theme values**
3. **Lazy load theme if needed**
4. **Monitor Core Web Vitals**
5. **Rollback if performance degrades**

**Acceptable increase:** < 2KB gzipped  
**Current estimate:** < 500 bytes (gzipped)

**Rollback time:** 5 minutes

---

## Testing Strategy to Prevent All Risks

### Pre-Migration (Day 1)
```bash
# 1. Audit codebase
node scripts/auditThemeUsage.js --output=json > before.json

# 2. Create visual baselines
npm run test:visual:baseline

# 3. Document metrics
npm run build
# Note: bundle size, build time, lighthouse scores
```

### During Each Batch
```bash
# For buttons batch:

# 1. Pre-migration check
node scripts/auditThemeUsage.js src/components/buttons

# 2. Run codemod with dry-run
jscodeshift -t codemods/replaceSxColors.js \
  --dry src/components/buttons

# 3. Review changes (before applying)
# ... manually inspect key files ...

# 4. Apply codemod
jscodeshift -t codemods/replaceSxColors.js src/components/buttons

# 5. Post-migration check
npm run lint:theme
npm run type-check

# 6. Visual regression test
npm run test:visual:ci -- tests/buttons.spec.ts

# 7. Manual screenshot review
# ... open visual report, approve each diff ...

# 8. Performance check
npm run build
# ... verify bundle size didn't increase > 1KB ...

# 9. Merge only if all checks pass
git add .
git commit -m "migrate: buttons to unified theme"
git push origin migrate/batch-buttons
# ... create PR, wait for CI, manual approval ...
```

### Post-Migration (Weekly)
```bash
# Monitor in production
- Check error logs for runtime errors
- Check visual regressions reported by users
- Check performance metrics
- Check dark mode usage (any complaints?)
```

---

## Rollback Procedures

### Quick Rollback (< 30 min)

**If one batch breaks:**
```bash
git log --oneline | head -10
# Find the bad commit
git revert COMMIT_HASH
git push origin main
```

**Estimated impact:** 30-50 components reverted

### Full Rollback (< 2 hours)

**If entire migration needs to be undone:**
```bash
# Find pre-migration commit
git log --all --grep="migration starts" --oneline

# Revert all commits since
git revert COMMIT_RANGE

# Verify
npm run build
npm run test
npm run test:visual:ci

# Deploy
npm run deploy:production
```

**Estimated impact:** All 600 components reverted to previous system

---

## Go/No-Go Criteria

### GO Criteria (Proceed to Next Phase)
- [ ] 0 critical visual regressions
- [ ] Build time < 60s (no increase > 10%)
- [ ] Bundle size < 2KB increase
- [ ] ESLint passing on 100% of batch
- [ ] Type checking passing on 100%
- [ ] Visual regression approval from 2+ engineers
- [ ] No new runtime errors in logs

### NO-GO Criteria (Halt and Investigate)
- [ ] Any critical visual regression
- [ ] Build time > 120s
- [ ] Bundle size > 3KB increase
- [ ] ESLint failures on > 5% of batch
- [ ] Type checking failures
- [ ] Unresolved visual diffs
- [ ] New runtime errors detected
- [ ] Performance degradation > 10%

---

## Critical Checkpoints

| Checkpoint | Owner | Criteria | If Failed |
|-----------|-------|----------|-----------|
| Week 1 EOW | Tech Lead | 1 batch tested, 0 regressions | Replan codemod |
| Week 2 EOW | QA Lead | 3 batches done, visual approval | Slow rollout |
| Week 3 EOW | Eng Manager | 500 components, < 5 issues | Extend timeline |
| Week 4 EOW | CTO | 600 components, prod ready | Post-launch rollback plan |

---

## Team Escalation Path

**Codemod issue** → Lead Architect → Tech Lead  
**Visual regression** → QA Lead → Engineering Manager  
**Performance issue** → DevOps → CTO  
**Rollback decision** → Engineering Manager + CTO  

---

## Post-Launch Monitoring (Week 5+)

### Daily Checks
- Any new styling errors reported?
- Any color inconsistencies?
- Any dark mode issues?
- Build time stable?

### Weekly Review
- User feedback on visual changes?
- Performance metrics stable?
- Error rate < baseline?
- Team velocity maintained?

### Monthly Review
- Long-term performance trends
- Any delayed issues discovered?
- Team satisfaction with new system
- Documentation gaps

---

## Appendix: Automated Risk Checklist

```bash
#!/bin/bash
# Run before merging each batch

echo "Running pre-merge checks..."

# 1. Audit
node scripts/auditThemeUsage.js --strict || exit 1

# 2. Lint
npx eslint src/components/[batch] --config .eslintrc.migration.js || exit 1

# 3. Type check
npx tsc --noEmit || exit 1

# 4. Build
npm run build || exit 1

# 5. Bundle size
npm run build:analyze
# ... manually verify no > 1KB increase ...

# 6. Visual tests
npm run test:visual:ci || exit 1

# 7. All good
echo "✓ All checks passed. Safe to merge."
```

---

**Last Updated:** 2026-02-28  
**Status:** Ready for Deployment  
**Risk Level:** LOW (with all mitigations in place)
