# Pilot Validation Plan: MUI Theme Migration
## 1-Week Validation Gate for 600+ Component Migration

**Status**: Ready to Execute  
**Duration**: 5-7 business days  
**Team Size**: 2-3 developers  
**Risk Level**: LOW (isolated, reversible)  
**Go/No-Go Decision**: End of Week 1

---

## EXECUTIVE SUMMARY

This pilot validates the **automated migration toolkit** (codemods, ESLint, visual regression) on a representative subset of 40-50 components before committing to migrating 600+ components over 4 weeks.

**Success criteria**: >90% codemod success, <5% manual intervention, zero regressions in pilot batch, predictable team velocity.

**Failure criteria**: <80% success, >15% manual intervention, visual regressions, type errors blocking deployment.

---

## SECTION 1: PILOT COMPONENT BATCH SELECTION

### Selection Criteria (Low-Risk, Representative)

**Size Range**: 40-50 components (5-8% of total scope)

**Component Types** (representative diversity):
- ✅ **8-12 Button variants** (simple, consistent patterns)
- ✅ **4-6 Form components** (TextField, Select, Checkbox) 
- ✅ **3-5 Card variants** (common layout component)
- ✅ **4-6 Dialog/Modal** (complex state, nested sx)
- ✅ **3-4 Table components** (data-heavy, styling complexity)
- ✅ **3-5 List/Menu components** (medium complexity)
- ✅ **2-3 Layout wrappers** (high reuse, propagation effect)

**Selection Rules**:
1. **No critical features** — Components not blocking active feature development
2. **High reuse** — Components used 10+ times across codebase (maximize downstream validation)
3. **Styling complexity** — Mix of simple + complex (test codemod range)
4. **Existing tests** — Prefer components with >80% test coverage (validate test stability)
5. **Low churn** — No active refactors/development in parallel

**Components to EXCLUDE**:
- Components in active feature branches
- Medical-specific critical components (Appointment Scheduler, PatientRecord)
- Performance-sensitive components (lists >1000 items)
- Third-party integrations
- Legacy components scheduled for removal

### Pilot Batch Composition

| Category | Count | Rationale |
|----------|-------|-----------|
| Buttons | 10 | Simple patterns, high reuse, validates basic sx/color mapping |
| Forms | 5 | Text inputs, selects, checkboxes — moderate complexity |
| Cards | 4 | Layout + shadows, validates shape/elevation overrides |
| Dialogs | 5 | Nested sx, Portal-based, validates complex selectors |
| Tables | 3 | Data-heavy, validates component overrides for MuiTableCell |
| Lists/Menu | 4 | Menu items, ListItems — medium nesting |
| Layouts | 3 | Wrappers, Stack, Grid — validates spacing propagation |
| **TOTAL** | **34-35** | Represents ~6% of codebase, covers all patterns |

### Exact Components to Include

**Recommended List** (adapt to your actual codebase):
- `components/buttons/PrimaryButton.tsx`
- `components/buttons/SecondaryButton.tsx`
- `components/buttons/DangerButton.tsx`
- `components/forms/TextInput.tsx`
- `components/forms/SelectDropdown.tsx`
- `components/forms/CheckboxGroup.tsx`
- `components/cards/PatientCard.tsx`
- `components/cards/AppointmentCard.tsx`
- `components/dialogs/ConfirmDialog.tsx`
- `components/dialogs/FormModal.tsx`
- `components/tables/DataTable.tsx`
- `components/lists/MenuBar.tsx`
- `components/layout/Header.tsx`
- `components/layout/Sidebar.tsx`

**[Fill in your specific component paths based on audit results]**

---

## SECTION 2: 5-DAY PILOT EXECUTION PLAN

### PRE-PILOT CHECKLIST (Day 0)

**Friday before pilot week** (1-2 hours):

- [ ] Create feature branch: `feature/theme-migration-pilot`
- [ ] Identify 40-50 pilot components (see Section 1)
- [ ] Create visual baseline: `npm run test:visual:baseline -- --components=pilot` (15 min)
- [ ] Document current metrics (ESLint errors, test coverage, build time)
- [ ] Brief team: Share pilot scope, timeline, rollback plan
- [ ] Notify QA: Visual regression testing will run continuously
- [ ] Create Slack channel: `#theme-migration-pilot`
- [ ] Prepare rollback checklist

**Baseline Metrics to Record**:
```
Build time: ___ seconds
ESLint errors: ___ (currently)
Test coverage: ___%
Failed tests: ___
Bundle size: ___ KB
```

---

### DAY 1 (MONDAY): SETUP & VALIDATION

**Duration**: 4-5 hours

#### 9:00 AM - 10:00 AM: Kickoff & Setup (1 hour)

- [ ] Team standup (15 min)
  - Review pilot scope, timeline, success criteria
  - Assign component batches to developers (if team of 2-3)
  - Confirm ESLint and visual regression CI is disabled (warnings only, not errors)
  
- [ ] Run audit script on pilot batch (15 min)
  ```bash
  node scripts/auditThemeUsage.js --components=pilot --output=pilot-baseline.json
  ```
  
- [ ] Verify all tools work (20 min)
  ```bash
  # Test dry-run of all codemods
  jscodeshift -t codemods/replaceSxColors.js --dry src/components/buttons/PrimaryButton.tsx
  jscodeshift -t codemods/normalizeSpacing.js --dry src/components/buttons/PrimaryButton.tsx
  jscodeshift -t codemods/replaceCssImports.js --dry src/components/buttons/PrimaryButton.tsx
  ```

#### 10:00 AM - 11:30 AM: Test Codemods on 2-3 Sample Components (1.5 hours)

- [ ] Apply codemods to first Button component (PrimaryButton)
  ```bash
  jscodeshift -t codemods/replaceSxColors.js src/components/buttons/PrimaryButton.tsx
  jscodeshift -t codemods/normalizeSpacing.js src/components/buttons/PrimaryButton.tsx
  ```

- [ ] Review changes
  - Manual code review (5 min)
  - Visual test in storybook or dev server (5 min)
  - Run tests: `npm test PrimaryButton.test.tsx` (5 min)
  - Document any issues

- [ ] Repeat on 1-2 more components (SelectDropdown, TextInput)

- [ ] **Identify Issues** and log in shared document:
  - Codemod misses (e.g., missed color refs)
  - Type errors
  - Broken imports
  - Visual regressions

#### 11:30 AM - 12:30 PM: Codemod Adjustments (1 hour)

- [ ] **If issues found**: Update codemods to fix common misses
  - Example: If codemod missed `backgroundColor` → add to pattern
  - Example: If spacing conversion was wrong → refine regex
  
- [ ] Re-test on same components with updated codemods
- [ ] Verify fixes work

#### 1:30 PM - 5:00 PM: Apply to Full Pilot Batch (3.5 hours)

- [ ] Apply all codemods to full 40-50 component batch
  ```bash
  jscodeshift -t codemods/replaceSxColors.js src/components/buttons
  jscodeshift -t codemods/replaceSxColors.js src/components/forms
  jscodeshift -t codemods/normalizeSpacing.js src/components
  jscodeshift -t codemods/replaceCssImports.js src/components
  ```

- [ ] Run tests on entire pilot batch
  ```bash
  npm test -- --testPathPattern="(buttons|forms|cards|dialogs|tables|lists|layout)"
  ```

- [ ] Document results in `PILOT_EXECUTION_LOG.md`

#### END OF DAY 1:
- [ ] Commit: `git commit -m "feat: apply migration codemods to pilot batch [automated]"`
- [ ] Record metrics (errors, test failures, manual fixes needed)

---

### DAY 2 (TUESDAY): MANUAL REVIEW & FIX

**Duration**: 5 hours

#### 9:00 AM - 10:30 AM: Code Review of Codemod Changes (1.5 hours)

- [ ] Review all changes from Day 1
  - Check for broken imports
  - Verify color mapping accuracy
  - Validate spacing grid adherence
  - Look for CSS-in-JS issues

- [ ] Document **manual interventions needed**:
  ```
  Issue Type | Count | Severity | Component(s) | Fix
  Missed color | 2 | Medium | Button.tsx | Manual map
  Wrong spacing | 1 | Low | Card.tsx | Adjust scale
  Type error | 3 | High | Dialog.tsx | Add useTheme()
  ```

#### 10:30 AM - 12:00 PM: Fix Manual Issues (1.5 hours)

- [ ] For each issue:
  1. Apply manual fix
  2. Run tests
  3. Document fix pattern for codemod improvement

- [ ] Record manual effort in shared spreadsheet

#### 1:00 PM - 3:00 PM: Type Checking & Compilation (2 hours)

- [ ] Run TypeScript compiler
  ```bash
  npx tsc --noEmit
  ```

- [ ] Fix any type errors
  - Missing `useTheme()` hook
  - Palette property misspellings
  - Deprecated MUI props

- [ ] Document types of errors for ESLint rules

#### 3:00 PM - 5:00 PM: Update ESLint Rules (2 hours)

- [ ] Based on Day 1-2 findings, update ESLint rules
  - Add rules to catch patterns codemods missed
  - Prepare rules for Week 3-4 enforcement (errors)

- [ ] Test ESLint on pilot batch
  ```bash
  npx eslint src/components --config .eslintrc.migration.js
  ```

#### END OF DAY 2:
- [ ] Commit: `git commit -m "fix: manual corrections post-migration [pilot day 2]"`
- [ ] Update metrics: manual fix count, type errors, ESLint violations

---

### DAY 3 (WEDNESDAY): VISUAL REGRESSION & TESTING

**Duration**: 5 hours

#### 9:00 AM - 11:00 AM: Visual Regression Testing (2 hours)

- [ ] Run visual regression baseline
  ```bash
  npm run test:visual:pilot
  ```

- [ ] Review all visual diffs
  - Light mode (compare before/after screenshots)
  - Dark mode (verify colors inverted correctly)
  - Hover/focus states (check interactions work)
  - Responsive breakpoints (verify mobile rendering)

- [ ] Document regressions:
  ```
  Component | Issue | Severity | Before | After | Root Cause
  Button | Color wrong | High | #1976d2 | #2196f3 | Codemod picked wrong variant
  Card | Shadow missing | Med | shadow-lg | shadow-md | Shape override not applied
  ```

#### 11:00 AM - 1:00 PM: Fix Visual Issues (2 hours)

- [ ] For each regression:
  1. Debug issue (theme override? component prop?)
  2. Apply fix
  3. Re-test visual

- [ ] Record if issue was:
  - Theme definition (fix in theme, not component)
  - Component override (fix in componentOverrides.ts)
  - Component usage (update component code)

#### 1:30 PM - 3:30 PM: Test Across Browsers & Devices (2 hours)

- [ ] Test in multiple browsers (Chrome, Firefox, Safari)
- [ ] Test responsive breakpoints (mobile, tablet, desktop)
- [ ] Test dark mode toggle (light ↔ dark)

- [ ] Document browser-specific issues

#### 3:30 PM - 5:00 PM: Performance Testing (1.5 hours)

- [ ] Measure before/after performance
  ```bash
  # Build time
  time npm run build
  
  # Bundle size
  npm run build && du -sh dist/
  
  # Lighthouse score
  npm run test:lighthouse
  ```

- [ ] Record metrics:
  ```
  Build time: ___ → ___ (change: ___)
  Bundle size: ___ → ___ (change: ___)
  Lighthouse: ___ → ___ (change: ___)
  ```

#### END OF DAY 3:
- [ ] Commit: `git commit -m "fix: visual regression corrections [pilot day 3]"`
- [ ] Update metrics: visual regression count, performance impact

---

### DAY 4 (THURSDAY): INTEGRATION & STABILITY

**Duration**: 4-5 hours

#### 9:00 AM - 11:00 AM: Integration Testing (2 hours)

- [ ] Run full test suite on pilot components
  ```bash
  npm test -- --testPathPattern="(buttons|forms|cards|dialogs|tables|lists|layout)"
  ```

- [ ] Record test results:
  - Passed: ___
  - Failed: ___
  - Skipped: ___

- [ ] Debug any failing tests

#### 11:00 AM - 12:30 PM: Rollback Drill (1.5 hours)

- [ ] **Dry-run rollback**:
  ```bash
  # Reset to baseline
  git reset --hard HEAD~20
  npm install
  npm test
  ```

- [ ] Verify rollback completes successfully
- [ ] Document rollback time: ___ minutes

#### 1:30 PM - 3:00 PM: Update Pilot Batch (1.5 hours)

- [ ] Re-apply fixes from Days 2-3 to current codebase
- [ ] Verify all fixes still apply cleanly

#### 3:00 PM - 5:00 PM: Production Readiness Check (2 hours)

- [ ] Checklist:
  - [ ] All tests passing
  - [ ] No TypeScript errors
  - [ ] ESLint warnings only (0 errors)
  - [ ] Visual regression < 2%
  - [ ] Performance impact < 5%
  - [ ] Documentation updated
  - [ ] Rollback procedure tested

- [ ] Sign-off from tech lead

#### END OF DAY 4:
- [ ] Commit: `git commit -m "chore: pilot validation complete, ready for review"`
- [ ] Prepare metrics report (see Section 3)

---

### DAY 5 (FRIDAY): METRICS & GO/NO-GO DECISION

**Duration**: 3-4 hours

#### 9:00 AM - 10:30 AM: Metrics Compilation (1.5 hours)

- [ ] Consolidate all measurements from Days 1-4
- [ ] Calculate success rates
- [ ] Generate visual summary (charts, tables)

#### 10:30 AM - 12:00 PM: Team Retrospective (1.5 hours)

- [ ] Gather developer feedback:
  - Codemod pain points
  - Manual fix patterns
  - Unforeseen issues
  - Suggestions for improvement

- [ ] Document in PILOT_RETROSPECTIVE.md

#### 1:00 PM - 3:00 PM: Go/No-Go Decision (2 hours)

- [ ] Review all metrics against criteria (see Section 4)
- [ ] Make GO or NO-GO decision
- [ ] If GO: Plan full 4-week migration
- [ ] If NO-GO: Plan corrective actions

- [ ] Brief stakeholders on decision

#### END OF WEEK:
- [ ] Create comprehensive PILOT_RESULTS.md
- [ ] Schedule full migration kickoff (if GO)
- [ ] OR plan codemod improvements (if NO-GO)

---

## SECTION 3: METRICS & MEASUREMENT

### Key Performance Indicators (KPIs)

#### 1. CODEMOD SUCCESS RATE

**Definition**: Percentage of pilot components where codemods successfully applied without manual intervention.

**Target**: ≥ 90%

**Measurement**:
```
Success Rate = (Components with 0 manual fixes / Total pilot components) × 100
```

**Recording Template**:
```
Component | Color Fixes | Spacing Fixes | CSS Fixes | Manual Edits | Status
Button.tsx | Auto | Auto | Auto | 0 | ✅ Success
Select.tsx | Auto | Auto | Manual | 1 | ⚠️ 1 fix
Card.tsx | Manual | Auto | Auto | 1 | ⚠️ 1 fix
```

#### 2. MANUAL INTERVENTION PERCENTAGE

**Definition**: Time spent on manual fixes vs. total development time.

**Target**: < 15%

**Measurement**:
```
Manual % = (Hours on manual fixes / Total pilot hours) × 100
```

**Time tracking**:
- Day 1: ___ hours codemod, ___ hours manual
- Day 2: ___ hours manual fixes, ___ hours review
- Day 3: ___ hours visual fixes
- Day 4: ___ hours integration fixes

**Total**: ___ hours on codemods, ___ hours on manual (= ___%)

#### 3. VISUAL REGRESSION RATE

**Definition**: % of pilot components with visual differences after migration.

**Target**: < 5% (acceptable regressions)

**Measurement**:
```
Regression Rate = (Components with visual issues / Total pilot components) × 100
```

**Categories**:
- No change: ___
- Minor (pixel-perfect differences): ___
- Moderate (noticeable but acceptable): ___
- Major (broken layout/colors): ___

#### 4. TYPE ERRORS INTRODUCED

**Definition**: Number of new TypeScript errors post-migration.

**Target**: 0 (or < 5 trivial)

**Measurement**:
```
Type Errors = Count of `npm tsc --noEmit` failures
Error Categories:
- Missing useTheme(): ___
- Palette property typos: ___
- Deprecated props: ___
- Import errors: ___
```

#### 5. TEST STABILITY

**Definition**: Test pass rate pre/post migration.

**Target**: 100% (or same as baseline)

**Measurement**:
```
Pre-migration: ___ passed, ___ failed
Post-migration: ___ passed, ___ failed
Change: ___
```

#### 6. PERFORMANCE IMPACT

**Definition**: Bundle size, build time, and Lighthouse changes.

**Target**: < 5% regression

**Measurements**:
```
Build time: ___ → ___ (+/- ___ %)
Bundle size: ___ KB → ___ KB (+/- ___ %)
Lighthouse: ___ → ___ (+/- ___ points)
```

#### 7. DEVELOPER VELOCITY

**Definition**: Estimated components per developer per day.

**Target**: 8-12 components/dev/day (for full migration planning)

**Measurement**:
```
Pilot velocity = (40 components) / (person-days spent) = ___ components/dev/day
```

---

### Measurement Recording Template

**File**: `PILOT_EXECUTION_LOG.md`

```markdown
# Pilot Execution Log

## Day 1: Setup & Codemods
- Components processed: 40
- Codemod success: ___/40 (___%)
- Manual edits needed: ___
- Build passes: YES/NO
- Tests pass: ___/___

## Day 2: Manual Review
- Manual fixes applied: ___
- Type errors: ___
- Time spent: ___ hours

## Day 3: Visual Testing
- Visual regressions found: ___
- Fixed: ___
- Remaining acceptable: ___

## Day 4: Integration
- Full test suite: ___% passing
- Rollback tested: YES/NO
- Time to rollback: ___ min

## Day 5: Metrics Summary
- **Codemod Success Rate**: ___%
- **Manual Intervention**: ___%
- **Visual Regression Rate**: ___%
- **Type Errors**: ___
- **Test Pass Rate**: ___%
- **Performance Impact**: ___%
- **Developer Velocity**: ___ components/dev/day

## Issues Found & Resolutions
| Issue | Severity | Root Cause | Resolution |
|-------|----------|-----------|-----------|
```

---

## SECTION 4: GO/NO-GO DECISION FRAMEWORK

### Success Criteria (ALL must pass for GO)

| Criterion | Target | Actual | Status |
|-----------|--------|--------|--------|
| Codemod success rate | ≥90% | ___% | ✅/❌ |
| Manual intervention | <15% | __% | ✅/❌ |
| Visual regression | <5% | __% | ✅/❌ |
| Type errors | <5 | ___ | ✅/❌ |
| Test pass rate | 100% | __% | ✅/❌ |
| Performance impact | <5% | __% | ✅/❌ |
| Rollback tested | YES | ___ | ✅/❌ |

### Decision Matrix

**GO Decision Criteria** ✅ (Proceed to full migration):
- Codemod success ≥ 90%
- Manual intervention < 15%
- Visual regressions < 5%
- Zero type errors blocking build
- Test pass rate ≥ 98%
- Performance within tolerance
- Rollback < 30 min confirmed
- Team confidence HIGH

**CONDITIONAL GO** ⚠️ (Proceed with modifications):
- Codemod success 80-89% (adjust codemods, proceed)
- Manual intervention 15-20% (add documentation, proceed)
- Visual regressions 5-10% (fix known issues, proceed)
- Small type errors (fix before proceeding)
- Team confidence MEDIUM

**NO-GO Decision Criteria** ❌ (Do not proceed, fix issues first):
- Codemod success < 80%
- Manual intervention > 25%
- Visual regressions > 15%
- Multiple type errors blocking build
- Test pass rate < 95%
- Rollback time > 60 min
- Performance regression > 10%
- Team confidence LOW

### Decision Approval

**Approvers** (sign-off required):
- [ ] Tech Lead (Architecture & Code Quality)
- [ ] QA Lead (Testing & Regressions)
- [ ] Engineering Manager (Timeline & Resource Impact)
- [ ] Product (No feature blockers)

**GO Decision**: Approved on ___ by ___

**Next Step**: 
- [ ] Schedule full migration kickoff
- [ ] Notify team of 4-week timeline
- [ ] Begin Week 1 (Batches 1-3)

OR

**NO-GO Decision**: Approved on ___ by ___

**Next Steps**:
- [ ] Identify root causes
- [ ] Plan codemod improvements
- [ ] Schedule re-assessment (1-2 weeks)

---

## SECTION 5: RISK SCORING MATRIX

### Post-Pilot Risk Assessment

Use these results to score risks for full 4-week migration.

#### Risk: Codemod Incompleteness

**Pilot Finding**: ___ % of issues required manual fixing

**Risk Score Adjustment**:
- If <10% → LOW RISK (minor tweaks OK)
- If 10-20% → MEDIUM RISK (need process for manual fixes)
- If >20% → HIGH RISK (may need different approach)

**Mitigation for Full Migration**:
- [ ] Add pair programming for complex components
- [ ] Create component-specific codemod variations
- [ ] Build checklist for common manual issues

#### Risk: Visual Regressions

**Pilot Finding**: ___ % of components had visual changes

**Risk Score Adjustment**:
- If <5% → LOW RISK (within tolerance)
- If 5-10% → MEDIUM RISK (need visual regression testing per batch)
- If >10% → HIGH RISK (theme overrides need review)

**Mitigation for Full Migration**:
- [ ] Require visual baseline for every 50-component batch
- [ ] Slower rollout (30 components/batch instead of 50)
- [ ] QA sign-off before each batch merge

#### Risk: Type System

**Pilot Finding**: ___ type errors introduced

**Risk Score Adjustment**:
- If 0 → LOW RISK (TypeScript is working well)
- If 1-5 → MEDIUM RISK (need pattern documentation)
- If >5 → HIGH RISK (missing types, need codemod adjustment)

**Mitigation for Full Migration**:
- [ ] Create TypeScript error checklist
- [ ] Document all error patterns found in pilot
- [ ] Add pre-commit type checking

#### Risk: Performance

**Pilot Finding**: ___ % change in build time, ___ % in bundle

**Risk Score Adjustment**:
- If <2% → LOW RISK (minimal impact)
- If 2-5% → MEDIUM RISK (monitor throughout)
- If >5% → HIGH RISK (investigate root cause)

**Mitigation for Full Migration**:
- [ ] Measure performance per batch
- [ ] Establish performance budget
- [ ] Require build time < X% for each batch

#### Risk: Team Velocity

**Pilot Finding**: ___ components per developer per day

**Risk Score Adjustment**:
- If >10 components/day → LOW RISK (can handle 4-week timeline)
- If 5-10 components/day → MEDIUM RISK (may need 5 weeks)
- If <5 components/day → HIGH RISK (may need 6+ weeks, more resources)

**Mitigation for Full Migration**:
- [ ] Allocate ___ developers for full migration
- [ ] Plan ___ weeks (based on pilot velocity)
- [ ] Have backup developers on standby

#### Overall Risk Score (Post-Pilot)

```
Risk Factor | Pilot Finding | Risk Level | Weight | Score
Codemod | ___% manual | L/M/H | 25% | ___
Visual | ___% regressions | L/M/H | 25% | ___
Type | ___ errors | L/M/H | 20% | ___
Performance | ___% impact | L/M/H | 15% | ___
Velocity | ___ comp/day | L/M/H | 15% | ___
TOTAL RISK: LOW / MEDIUM / HIGH
```

---

## SECTION 6: CODEMOD ADJUSTMENTS BASED ON PILOT

### Common Issues Found in Pilot & Fixes

#### Issue #1: Color Mapping Misses

**Problem**: Codemod missed certain color properties (e.g., `borderColor`, `outlineColor`)

**Pilot Finding**: Affected ___ components

**Fix Applied**:
- [ ] Update regex in `replaceSxColors.js` to include all CSS color properties
- [ ] Add these patterns to codemod:
  ```javascript
  borderColor, outlineColor, caretColor, accentColor, columnRuleColor, textDecorationColor
  ```
- [ ] Re-test on failed components

#### Issue #2: Spacing Conversion Edge Cases

**Problem**: Codemod converted `padding: '8px'` → `padding: 1` but should be `padding: 2` (16px ≠ 8px)

**Pilot Finding**: Affected ___ components

**Fix Applied**:
- [ ] Update spacing conversion table
- [ ] Document exceptions (e.g., 6px, 9px, 14px that don't map cleanly)
- [ ] Add manual review step for non-standard spacing

#### Issue #3: CSS-in-JS with Complex Selectors

**Problem**: Codemod couldn't convert `'& .MuiButton-root': { ... }`

**Pilot Finding**: Affected ___ components

**Fix Applied**:
- [ ] Create separate codemod for nested selectors
- [ ] Or: Flag for manual review instead of breaking conversion

#### Issue #4: Conditional/Ternary Spacing

**Problem**: Codemod couldn't handle `padding: responsive ? '16px' : '8px'`

**Pilot Finding**: Affected ___ components

**Fix Applied**:
- [ ] Improve regex to handle ternary operations
- [ ] Or: Document as manual-fix pattern, teach team workaround

### Codemod Improvements (Before Full Migration)

**Priority 1 - Fix Before Full Migration**:
- [ ] Issue #1 (color mapping) — affects ALL components
- [ ] Issue #2 (spacing edge cases) — affects FORM components
- [ ] Issue #3 (CSS selectors) — affects DIALOG/MODAL components

**Priority 2 - Document for Manual Handling**:
- [ ] Issue #4 (ternary spacing) — rare, can be handled manually

**Updated Codemods Ready Before Week 1 Full Migration**: YES/NO

---

## SECTION 7: DEVELOPER WORKFLOW DURING PILOT

### Branch & Commit Strategy

**Feature branch**: `feature/theme-migration-pilot`

**Commit history** (descriptive):
```
Day 1:
  feat: apply color/spacing codemods to pilot batch [automated]
  
Day 2:
  fix: manual color mapping corrections [pilot day 2]
  fix: missing useTheme hooks in dialogs [pilot day 2]
  
Day 3:
  fix: visual regression corrections [pilot day 3]
  
Day 4:
  test: integration test results [pilot day 4]
```

**Do NOT commit**:
- Merging to `main` before Day 5 decision
- Changing theme files (theme is locked for pilot)
- Adding new components to pilot batch mid-week

### Handling Merge Conflicts

**If someone changes pilot components while pilot is running**:

1. **Daily sync** (9:00 AM each day)
   - Pull latest from `main` into pilot branch
   - Resolve conflicts (usually spacing/imports)
   - Test doesn't break

2. **Hot-fix process** (if critical bug found in pilot component)
   - Apply fix to both `main` and pilot branch
   - Document in pilot log

3. **New feature in pilot component** (block until after pilot)
   - Notify engineer: component is in pilot, hold off on features
   - Proceed with features after pilot ends (Day 5+)

### Communication

**Daily 9:00 AM standup** (15 min):
- What was done yesterday
- What will be done today
- Any blockers

**Daily 5:00 PM status** (5 min async):
- Metrics update in shared spreadsheet
- Issues logged
- Go/No-Go confidence level

---

## SECTION 8: CI/CD STRATEGY DURING PILOT

### ESLint & Type Checking

**During Pilot (Days 1-5)**:
- ESLint: **WARNINGS ONLY** (no errors, don't block merge)
- TypeScript: **STRICT TYPE** (catch errors early)
- Tests: **MUST PASS** (can't merge if tests fail)
- Build: **MUST SUCCEED** (can't merge if build fails)

**Configuration**:
```javascript
// .eslintrc.migration.js - PILOT MODE
{
  "rules": {
    "no-hardcoded-colors": "warn",      // Warning
    "no-hardcoded-spacing": "warn",     // Warning
    "prefer-theme-values": "warn",      // Warning
  }
}
```

### CI Checks During Pilot

| Check | Status | Blocks Merge? |
|-------|--------|---------------|
| ESLint | ⚠️ Warnings | NO |
| TypeScript | ✅ Strict | YES |
| Tests | ✅ All pass | YES |
| Build | ✅ Succeeds | YES |
| Visual Regression | ⚠️ Report | NO (info only) |
| Performance | ⚠️ Report | NO (info only) |

### After Pilot (Week 2+ of full migration)

**Transition to stricter enforcement**:
```javascript
// .eslintrc.migration.js - WEEK 2 HARDENING
{
  "rules": {
    "no-hardcoded-colors": "error",     // Error - blocks merge
    "no-hardcoded-spacing": "error",    // Error - blocks merge
  }
}
```

---

## SECTION 9: ROLLBACK STRATEGY

### Quick Rollback (< 30 minutes)

**If pilot is deemed NO-GO on Day 5**:

```bash
# Step 1: Switch to main (2 min)
git checkout main
git pull

# Step 2: Verify no pilot code in production (2 min)
npm install
npm build

# Step 3: Run tests to confirm stability (5 min)
npm test

# Step 4: Deploy main back to staging (5 min)
# [Your deployment process here]

# Step 5: Verify in staging (5 min)
# Spot checks on buttons, forms, dialogs
```

**Total rollback time**: ~25 minutes

### Full Rollback (if issues found mid-pilot)

**If day 2-3 finds critical issues**:

1. **Pause codemod application** (stop applying to remaining components)
2. **Rollback to start of day** (revert last commits)
3. **Debug issue** (1-2 hours)
4. **Fix codemod** (1-2 hours)
5. **Resume** (from last good state)

### Prevention

**Safeguards to avoid needing rollback**:
- [ ] All code changes on feature branch (main is safe)
- [ ] Daily backups of `PILOT_EXECUTION_LOG.md`
- [ ] Commit after each day (easy to revert to previous day)
- [ ] Visual baseline preserved (before/after comparison always available)

---

## SECTION 10: COMMUNICATION PLAN

### Pre-Pilot (Friday before)

**Slack announcement** (#engineering):
```
🚀 Theme Migration Pilot Starting Monday!

Pilot scope:
- 40-50 components (Buttons, Forms, Cards, Dialogs, Tables)
- Validation of automated migration codemods
- GO/NO-GO decision by Friday EOD

Timeline:
- Mon-Thu: Execution & testing
- Fri: Metrics & decision

Feature development:
- Continue as normal OUTSIDE pilot components
- Hold off on changes to pilot components during pilot week

Questions? Ask in #theme-migration-pilot

cc: @engineers @qa @product
```

### Daily (Mon-Fri)

**9:00 AM standup** (Slack thread):
```
Day 1 Update:
✅ All codemods applied to pilot batch
✅ 92% success rate (no manual fixes yet)
⏳ 2 type errors found, investigating

Blocker: None
Confidence: 🟢 HIGH
```

**5:00 PM metrics update** (shared spreadsheet):
```
Date | Codemods | Manual Fixes | Visual Issues | Type Errors | Notes
----+----------+--------------+---------------+-------------+------
Mon | 40/40 ✅ | 0 | TBD | 2 | Need useTheme()
```

### Friday (Go/No-Go)

**Final briefing** (Slack):
```
📊 PILOT RESULTS - DECISION TIME

Metrics Summary:
✅ Codemod Success: 92%
✅ Manual Intervention: 8%
✅ Visual Regressions: 2%
✅ Type Errors: 0
✅ Tests Passing: 100%

Decision: **GO** ✅

Next Steps:
1. Week 1 (starting Monday): Batches 1-3
2. Expect 4 weeks total for 600+ components
3. Full migration kickoff call: Monday 2pm

Details: See PILOT_RESULTS.md in repo
```

### Weekly (Full Migration Phase)

**Batch completion report** (Monday AM):
```
Week 1 Complete ✅
- Batches completed: 1, 2, 3
- Components migrated: 90 (15% of total)
- Issues found: 3 (all fixed)
- On track for finish: Week 4

Week 2 Preview:
- Batches: 4, 5, 6, 7
- Estimated components: 200+
```

---

## APPENDIX A: PILOT CHECKLIST

### Pre-Pilot (Friday)
- [ ] Feature branch created: `feature/theme-migration-pilot`
- [ ] Pilot batch identified (40-50 components)
- [ ] Visual baseline captured
- [ ] All codemods tested in dry-run
- [ ] Team briefed on pilot
- [ ] Rollback procedure tested
- [ ] Slack channel created: `#theme-migration-pilot`
- [ ] Success criteria documented
- [ ] Decision framework agreed upon

### Daily Checklist (Mon-Fri)

**Start of Day**:
- [ ] Pull latest from main
- [ ] Resolve any merge conflicts
- [ ] Quick test of tools (codemods, audit script)
- [ ] Update team on Slack

**During Day**:
- [ ] Apply codemods to assigned components
- [ ] Run tests after each component
- [ ] Document issues in shared log
- [ ] Take screenshots for visual regression
- [ ] Update metrics spreadsheet (EOD)

**End of Day**:
- [ ] Commit changes with descriptive message
- [ ] Push to feature branch
- [ ] Post metrics update to Slack
- [ ] Flag any blockers

### Friday End of Pilot
- [ ] All metrics compiled
- [ ] Team retrospective completed
- [ ] GO/NO-GO decision made
- [ ] Sign-off from tech lead, QA, PM
- [ ] PILOT_RESULTS.md created
- [ ] Full migration plan ready (if GO)

---

## APPENDIX B: SAMPLE SUCCESS METRICS

### Example: Pilot Shows GO

```
# PILOT RESULTS - GO DECISION

Metrics:
✅ Codemod Success Rate: 92% (37/40 components)
✅ Manual Intervention: 8% (3.2 hours out of 40 hours)
✅ Visual Regression Rate: 2% (1 component, minor shadow issue)
✅ Type Errors: 0 (after 2 fixes on Day 2)
✅ Test Pass Rate: 100% (all tests passing)
✅ Performance Impact: +0.5% (negligible)
✅ Rollback Time: 22 minutes (verified)

Velocity:
- Estimated: 40 components in 4 days = 10 components/dev/day
- Full Migration: 600 components ÷ 10/day ÷ 3 devs = 20 days = 4 weeks ✅

Decision: **GO** ✅
- Tech Lead: APPROVED ✅
- QA: APPROVED ✅
- Engineering Manager: APPROVED ✅
- Product: APPROVED ✅

Next: Full migration kickoff Monday 2pm
```

### Example: Pilot Shows NO-GO

```
# PILOT RESULTS - NO-GO DECISION

Metrics:
❌ Codemod Success Rate: 73% (29/40 components)
❌ Manual Intervention: 27% (10.8 hours out of 40 hours)
⚠️ Visual Regression Rate: 12% (5 components with color issues)
⚠️ Type Errors: 7 (palette references, useTheme issues)
✅ Test Pass Rate: 98% (1 test failing)
❌ Performance Impact: +8% (above tolerance)

Blockers:
1. Codemod misses ~25% of color edge cases
2. Spacing conversion has false positives
3. Theme palette structure unclear to devs
4. Performance regression unexplained

Decision: **NO-GO** ❌
- Tech Lead: REJECTED - needs codemod improvements
- QA: HOLD - visual regressions need investigation
- Engineering Manager: HOLD - timeline risk if velocity continues
- Product: APPROVED (features not blocked)

Next Steps:
1. Root cause: Spacing conversion is adding 15KB
2. Codemod improvements: Add more color patterns, fix spacing logic
3. Retesting: 1-2 weeks
4. Re-assessment: [Date]
```

---

## DOCUMENT CONTROL

**Version**: 1.0  
**Created**: [Date]  
**Status**: Ready to Execute  
**Owner**: [Tech Lead Name]  
**Next Review**: End of Pilot (Day 5)

**Document Location**: `/frontend/PILOT_VALIDATION_PLAN.md`

---

**You are now ready to execute a professional, low-risk pilot validation. Execute with confidence!**
