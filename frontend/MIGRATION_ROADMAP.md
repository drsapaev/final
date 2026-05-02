# 600-Component Theme Migration Roadmap

## Executive Summary

This document outlines a 4-week automated migration strategy to safely refactor 600+ components from scattered styling approaches to the unified MUI v5 theme system. The approach minimizes manual work using jscodeshift codemods and automated enforcement.

---

## Week-by-Week Execution Plan

### **WEEK 1: Foundation & Codemod Testing**

#### Monday-Tuesday: Baseline & Test Codemods
- Run `node scripts/auditThemeUsage.js` to generate baseline report
- Test codemods on 5-10 volunteer components
- Identify color mapping gaps
- Create final color mapping reference

**Deliverables:**
- Audit baseline report
- Tested codemod set
- Updated color mappings

#### Wednesday-Thursday: Prepare CI/ESLint
- Set up migration ESLint rules in warning mode
- Configure pre-commit hooks
- Brief team on new rules
- Set up visual regression testing baseline

**Deliverables:**
- ESLint warnings in pre-commit
- CI pipeline updated
- Team trained on new patterns

#### Friday: Run First Batch
- Auto-migrate components in `/components/buttons/` (assumed ~30 components)
- Manually review all changes
- Deploy to staging and test visually
- Document learnings

**Team allocation:** 1 lead dev + 2 QA  
**Expected result:** 30 components automated, zero regressions

---

### **WEEK 2: High-Volume Automation**

#### Monday-Wednesday: Batch 2-4 Automation
- `components/form/` (~80 components)
- `components/layout/` (~60 components)
- `components/cards/` (~40 components)

**For each batch:**
1. Run jscodeshift codemod
2. Audit output
3. Manual code review (sample 10%)
4. Visual regression test
5. Merge and deploy

**Batch command example:**
```bash
jscodeshift -t codemods/replaceSxColors.js src/components/form
jscodeshift -t codemods/normalizeSpacing.js src/components/form
node scripts/auditThemeUsage.js --strict
```

#### Thursday-Friday: Mid-Migration Review
- Run full audit again
- Measure progress
- Adjust mappings if needed
- Address failures from weeks 1-2

**Expected result:** 210+ components automated

---

### **WEEK 3: Remaining Components & Enforcement**

#### Monday-Wednesday: Final Large Batches
- `components/tables/` (~50 components)
- `components/dialogs/` (~40 components)
- `components/menus/` (~60 components)
- Misc utilities and helpers (~100 components)

#### Thursday: ESLint Rule Hardening
- Switch ESLint rules from 'warn' to 'error' (gradual)
- Only for freshly migrated areas first
- Allow documented bypass comments
- Monitor CI failures

#### Friday: Compliance Check
- Automated audit of all 600 components
- 100% pass rate required for auto-migration
- Manual review of 20% sample
- Document edge cases for phase 4

**Expected result:** 500+ components automated, 100 manually reviewed

---

### **WEEK 4: Hardening & Final Rollout**

#### Monday-Tuesday: Edge Cases & Finals
- Identify remaining components needing manual work
- Create specific refactoring guide for each type
- Allocate manual dev time for complex cases
- Update documentation

#### Wednesday-Thursday: Full Enforcement
- All ESLint rules to 'error'
- Update code review checklist
- Train team on code review
- Deploy to production

#### Friday: Stabilization & Monitoring
- Monitor production for visual regressions
- Address any issues
- Prepare retrospective
- Document migration success

**Expected result:** 100% theme migration complete, zero breaking changes

---

## Automation Details

### Codemod Commands

#### Replace Hardcoded Colors
```bash
jscodeshift -t codemods/replaceSxColors.js \
  --parser=babel \
  --parser-options='ecmaVersion: 2020, sourceType: module, ecmaFeatures: { jsx: true }' \
  src/components/
```

#### Normalize Spacing
```bash
jscodeshift -t codemods/normalizeSpacing.js \
  --parser=babel \
  --parser-options='ecmaVersion: 2020, sourceType: module, ecmaFeatures: { jsx: true }' \
  src/components/
```

#### Remove Legacy CSS Imports
```bash
jscodeshift -t codemods/replaceCssImports.js \
  --parser=babel \
  --parser-options='ecmaVersion: 2020, sourceType: module, ecmaFeatures: { jsx: true }' \
  src/components/
```

### Audit Commands

**Baseline audit:**
```bash
node scripts/auditThemeUsage.js --output=json > audit-baseline.json
```

**Strict mode (fails on any error):**
```bash
node scripts/auditThemeUsage.js --strict
```

**After each migration batch:**
```bash
node scripts/auditThemeUsage.js --strict
```

---

## Risk Mitigation

### What Can Break

1. **Color Mapping Misses**
   - Risk: Wrong color applied
   - Mitigation: Visual regression tests catch 100%
   - Rollback: Git revert the batch

2. **Spacing Calculation Errors**
   - Risk: Layout shifts
   - Mitigation: Compare screenshots before/after
   - Rollback: Git revert the batch

3. **Missing useTheme() Imports**
   - Risk: Runtime error
   - Mitigation: Codemod adds imports automatically
   - Rollback: Audit script catches all cases

4. **Removed CSS Causing Side Effects**
   - Risk: Styles missing entirely
   - Mitigation: Manual review before merge
   - Rollback: Git restore CSS files

### Safety Procedures

**Before each batch migration:**
```bash
# 1. Create backup branch
git checkout -b migrate/batch-N

# 2. Run audit to get baseline
node scripts/auditThemeUsage.js --output=json > before.json

# 3. Run codemods
jscodeshift -t codemods/replaceSxColors.js src/components/X
jscodeshift -t codemods/normalizeSpacing.js src/components/X

# 4. Verify no new violations
node scripts/auditThemeUsage.js --strict

# 5. Manual review (key files only)
git diff src/components/X | head -500

# 6. Visual regression test
npm run test:visual:snapshot

# 7. Merge only if all tests pass
git checkout main && git merge migrate/batch-N
```

**Rollback procedure** (if something breaks):
```bash
# 1. Identify problematic batch
git log --oneline | head -5

# 2. Revert
git revert COMMIT_HASH

# 3. Fix codemod mapping
# ... update codemods/replaceSxColors.js

# 4. Test fix
jscodeshift -t codemods/replaceSxColors.js src/components/X

# 5. Re-merge
git cherry-pick COMMIT_HASH
```

---

## Team Allocation

### Phase 1 (Week 1): Discovery
- 1 Lead Architect (oversee codemods)
- 2 Senior Devs (test codemods, code review)
- 1 QA Engineer (visual regression)

### Phase 2 (Week 2-3): Execution
- 1 Codemod Operator (runs batch migrations)
- 2 Code Reviewers (spot-check outputs)
- 2 QA Engineers (visual tests)
- 1 Tech Lead (oversight)

### Phase 3 (Week 4): Hardening
- 2 Manual Refactorers (complex edge cases)
- 1 Code Review Lead (enforce standards)
- 1 QA Lead (final verification)

**Total effort:** ~2-3 developer weeks

---

## Success Criteria

### Code Coverage
- [ ] 600+ components migrated
- [ ] 100% violations fixed
- [ ] 0 hardcoded colors in codebase
- [ ] 0 non-standard spacing values
- [ ] All CSS imports removed

### Quality
- [ ] 0 visual regressions in staging
- [ ] All components tested in light + dark mode
- [ ] 100% accessibility maintained (WCAG AA)
- [ ] Build time unchanged

### Process
- [ ] ESLint rules passing on CI
- [ ] Pre-commit hooks catch violations
- [ ] Code review checklist updated
- [ ] Team trained on new patterns
- [ ] Documentation complete

---

## Monitoring & Enforcement

### Post-Migration (Week 5+)

**Daily checks:**
```bash
# Run in CI
npm run audit:theme --strict
```

**Weekly team standup:**
- Any new hardcoded colors detected?
- Any ESLint bypasses used?
- Any visual inconsistencies reported?

**Monthly review:**
- Audit trends
- Team velocity on theme-aware components
- Update documentation as needed

---

## Rollback Plan

If entire migration needs to be undone:

```bash
# 1. Identify pre-migration commit
git log --grep="migration" --oneline

# 2. Revert all migration commits
git revert COMMIT_RANGE

# 3. Restore original ESLint config
git checkout main .eslintrc.migration.js

# 4. Remove migration codemods (optional)
rm -rf codemods/

# 5. Verify build
npm run build

# 6. Deploy rollback
# Follow standard deployment procedure
```

**Estimated rollback time:** 30 minutes  
**Likelihood:** < 5% (with proper testing)

---

## Appendix: Batch Component Estimates

| Folder | Est. Components | Est. Issues | Codemod % | Manual % |
|--------|-----------------|-------------|-----------|----------|
| buttons | 30 | 45 | 90% | 10% |
| form | 80 | 120 | 85% | 15% |
| layout | 60 | 80 | 80% | 20% |
| cards | 40 | 50 | 95% | 5% |
| tables | 50 | 100 | 75% | 25% |
| dialogs | 40 | 60 | 85% | 15% |
| menus | 60 | 90 | 80% | 20% |
| utils | 40 | 30 | 85% | 15% |
| **TOTAL** | **400** | **575** | **84%** | **16%** |

---

## Contact & Escalation

- **Week 1 Questions?** → Tech Lead
- **Codemod Failures?** → Lead Architect
- **Visual Regressions?** → QA Lead
- **Rollback Decision?** → Engineering Manager

---

**Status:** Ready for Deployment  
**Created:** 2026-02-28  
**Version:** 1.0
