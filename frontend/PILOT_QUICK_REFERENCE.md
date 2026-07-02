# Pilot Validation: Quick Reference Guide

**Print this page and keep at your desk during the pilot week.**

---

## 🎯 PILOT AT A GLANCE

| Item | Details |
|------|---------|
| **Duration** | 5 business days (Mon-Fri) |
| **Team** | 2-3 developers |
| **Components** | 40-50 pilot batch |
| **Success Target** | GO decision by Friday EOD |
| **Risk Level** | LOW (reversible, isolated) |

---

## ✅ SUCCESS CRITERIA (ALL must pass for GO)

```
✅ Codemod Success:         ≥ 90%   (actual: __%)
✅ Manual Intervention:     < 15%   (actual: __%)
✅ Visual Regression:       < 5%    (actual: __%)
✅ Type Errors:             < 5     (actual: ___)
✅ Test Pass Rate:          100%    (actual: __%)
✅ Performance Impact:      < 5%    (actual: __%)
✅ Rollback Time:           < 30min (actual: __ min)
```

**Confidence**: 🟢 HIGH / 🟡 MEDIUM / 🔴 LOW

---

## 📅 5-DAY TIMELINE

### **DAY 1 (MONDAY): Setup & Codemods**
- ✅ Team kickoff (9:00 AM)
- ✅ Audit baseline (10:00 AM)
- ✅ Test codemods on 2-3 samples (10:30 AM)
- ✅ Apply to full pilot batch (1:30 PM)
- 📊 Metrics: Success rate, manual fixes needed

### **DAY 2 (TUESDAY): Manual Review & Fixes**
- ✅ Code review of all changes (9:00 AM)
- ✅ Apply manual fixes (10:30 AM)
- ✅ TypeScript check & fix errors (1:00 PM)
- ✅ Update ESLint rules (3:00 PM)
- 📊 Metrics: Manual % of time, type errors fixed

### **DAY 3 (WEDNESDAY): Visual Testing**
- ✅ Visual regression baseline (9:00 AM)
- ✅ Fix visual issues (11:00 AM)
- ✅ Cross-browser testing (1:30 PM)
- ✅ Performance testing (3:30 PM)
- 📊 Metrics: Visual regression %, build/bundle impact

### **DAY 4 (THURSDAY): Integration**
- ✅ Full test suite run (9:00 AM)
- ✅ Rollback drill (11:00 AM)
- ✅ Re-apply fixes verification (1:30 PM)
- ✅ Production readiness check (3:00 PM)
- 📊 Metrics: Test stability, rollback time

### **DAY 5 (FRIDAY): Decision**
- ✅ Compile all metrics (9:00 AM)
- ✅ Team retrospective (10:30 AM)
- ✅ GO/NO-GO decision (1:00 PM)
- ✅ Brief stakeholders (3:00 PM)
- 🚀 **GO**: Start full migration Monday
- 🛑 **NO-GO**: Plan improvements, reschedule

---

## 🛠️ ESSENTIAL COMMANDS

### Audit Baseline (Day 1)
```bash
node scripts/auditThemeUsage.js --components=pilot --output=pilot-baseline.json
```

### Apply Codemods (Day 1)
```bash
jscodeshift -t codemods/replaceSxColors.js src/components/buttons
jscodeshift -t codemods/normalizeSpacing.js src/components
jscodeshift -t codemods/replaceCssImports.js src/components
```

### Run Tests (All days)
```bash
npm test -- --testPathPattern="(buttons|forms|cards|dialogs|tables|lists|layout)"
```

### Type Check (Day 2)
```bash
npx tsc --noEmit
```

### ESLint Check (Day 2)
```bash
npx eslint src/components --config .eslintrc.migration.js
```

### Visual Regression (Day 3)
```bash
npm run test:visual:pilot
```

### Build & Performance (Day 3)
```bash
npm run build
npm run test:lighthouse
```

### Rollback Drill (Day 4)
```bash
git reset --hard HEAD~20
npm install
npm test
```

---

## 📊 METRICS TO TRACK

### Daily Spreadsheet (Update 5 PM each day)

```
Date  | Batch | Codemods | Manual | Visual | TypeErr | Tests | Blocker
------|-------|----------|--------|--------|---------|-------|----------
Mon   | 40    | ✅       | ___    | TBD    | __      | TBD   | None
Tue   | 40    | ✅       | ✅     | TBD    | ✅      | TBD   | None
Wed   | 40    | ✅       | ✅     | ✅     | ✅      | TBD   | None
Thu   | 40    | ✅       | ✅     | ✅     | ✅      | ✅    | None
Fri   | 40    | ✅       | ✅     | ✅     | ✅      | ✅    | GO/NO-GO
```

### Calculate at End of Each Day

- **Codemod Success %** = (Components with 0 manual fixes / Total) × 100
- **Manual %** = (Hours manual / Total hours) × 100
- **Visual Regression %** = (Components with issues / Total) × 100

---

## 🐛 COMMON ISSUES & FIXES

### Issue: Codemod misses hardcoded color
**Solution**: Update regex in codemod, re-run, or add to manual fixes

### Issue: Spacing converts to wrong value
**Solution**: Check spacing scale mapping, apply manual adjustment

### Issue: TypeScript: Property not found on palette
**Solution**: Add `useTheme()` hook, or check palette structure

### Issue: Visual change after migration
**Solution**: Check if theme override applied, or revert component sx

### Issue: Test failure post-migration
**Solution**: Verify color values match, check theme context available

---

## 📋 DAILY CHECKLIST

### Morning (9:00 AM)
- [ ] Pull latest main to pilot branch
- [ ] Run quick test: `npm test -- Button.test.tsx`
- [ ] Update team on Slack

### During Day
- [ ] Apply codemods (batch by batch)
- [ ] Run tests after each batch
- [ ] Document issues in execution log
- [ ] Verify build succeeds
- [ ] Take screenshots for visual (Day 3+)

### Evening (5:00 PM)
- [ ] Update metrics spreadsheet
- [ ] Commit changes with descriptive message
- [ ] Post summary to Slack
- [ ] Flag any blockers

---

## 🚨 RED FLAGS (Stop & Escalate)

| Red Flag | Action |
|----------|--------|
| Build fails to compile | Stop, debug, don't merge |
| >20% codemod failures | Pause, review codemods, adjust |
| >10 type errors introduced | Debug types, don't proceed |
| Major visual regressions (>10%) | Investigate theme overrides |
| Test pass rate < 95% | Fix failing tests before Day 4 |
| Rollback takes > 60 minutes | Investigate, create faster rollback |

---

## 📞 WHO TO CONTACT

| Issue Type | Contact | When |
|-----------|---------|------|
| Codemod problems | [Dev Lead] | Immediately |
| Type errors | [Type specialist] | End of day |
| Visual issues | [QA Lead] | Day 3 |
| Performance concerns | [Infra Lead] | Day 3 EOD |
| Blocker / decision | [Tech Lead] | Immediately |

---

## 🎯 DECISION FRAMEWORK (Friday)

### **GO if:**
- ✅ Codemod success ≥ 90%
- ✅ Manual intervention < 15%
- ✅ Visual regressions < 5%
- ✅ Type errors < 5
- ✅ Tests passing ≥ 98%
- ✅ Performance < 5% impact
- ✅ Team confidence HIGH 🟢

### **NO-GO if:**
- ❌ Codemod success < 80%
- ❌ Manual intervention > 25%
- ❌ Visual regressions > 15%
- ❌ Type errors > 10
- ❌ Tests failing > 5
- ❌ Performance > 10% impact
- ❌ Team confidence LOW 🔴

### **CONDITIONAL (proceed with care):**
- 80-89% codemod success → adjust codemods, GO
- 15-20% manual → add documentation, GO
- 5-10% visual regressions → fix known issues, GO

---

## 📝 GIT WORKFLOW

**Branch**: `feature/theme-migration-pilot`

**Daily commits**:
```
Day 1: feat: apply migration codemods to pilot batch [automated]
Day 2: fix: manual corrections post-migration [pilot day 2]
Day 3: fix: visual regression corrections [pilot day 3]
Day 4: chore: pilot validation complete, ready for review
Day 5: docs: pilot results, decision documented
```

**DO NOT**:
- ❌ Merge to main before Day 5 decision
- ❌ Modify theme files during pilot
- ❌ Add new pilot components mid-week
- ❌ Commit without descriptive message

---

## 📞 SLACK UPDATES

### Daily 9:00 AM (standup)
```
Day 1 Update:
✅ Codemods applied to 40 components
⏳ Reviewing for manual fixes
Confidence: 🟢 HIGH
```

### Daily 5:00 PM (metrics)
```
EOD Metrics:
- Codemod Success: 92% (37/40)
- Manual Fixes: 3
- Tests: ✅ PASS
- Build: ✅ PASS
Blocker: None
```

### Friday 3:00 PM (decision)
```
📊 PILOT DECISION: GO ✅

Metrics:
✅ Codemod: 92%
✅ Manual: 8%
✅ Visual: 2%
✅ Types: 0
✅ Tests: 100%

Full migration starts Monday!
cc: @team
```

---

## 📞 SUPPORT RESOURCES

- **PILOT_VALIDATION_PLAN.md** — Complete 50-page plan (reference)
- **PILOT_EXECUTION_LOG.md** — Fill in as you go (working document)
- **MIGRATION_TOOLKIT_SUMMARY.md** — Context & tools overview
- **AUTOMATED_MIGRATION_GUIDE.md** — Detailed command reference

---

**Print this page. Keep it visible during pilot week. Reference it daily.**

**You've got this! 🚀**
