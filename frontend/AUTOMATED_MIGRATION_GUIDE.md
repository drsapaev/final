# Automated Migration Implementation Guide

Complete step-by-step guide for executing the 600-component theme migration using codemods and automation.

---

## Prerequisites

```bash
# Install required tools
npm install --save-dev jscodeshift @babel/parser @babel/types
npm install --save-dev glob

# Verify installation
npx jscodeshift --version
node scripts/auditThemeUsage.js --help
```

---

## Step 1: Pre-Migration Audit (Day 1)

### 1.1 Generate Baseline Report

```bash
# Create audit baseline
node scripts/auditThemeUsage.js --output=json > audit-baseline.json

# View in readable format
node scripts/auditThemeUsage.js
```

**Expected output:**
```
Files Scanned: 434
Violations: 287
Warnings: 156

HARDCODED_HEX: 187 issue(s)
INLINE_RGBA: 34 issue(s)
INLINE_STYLE_COLOR: 45 issue(s)
NON_STANDARD_SPACING: 78 issue(s)
```

### 1.2 Analyze Color Usage

```bash
# Find all hardcoded colors
grep -r "#[0-9a-fA-F]\{6\}" src/components --include="*.jsx" --include="*.tsx" | \
  sed 's/.*#//' | cut -d: -f2 | sort | uniq -c | sort -rn > colors-used.txt

# Review most common colors
head -20 colors-used.txt
```

**Example output:**
```
15 #1976d2  -> theme.palette.primary.main
12 #dc2626  -> theme.palette.error.main
 8 #388e3c  -> theme.palette.success.main
...
```

### 1.3 Create Color Mapping Reference

```javascript
// codemods/colorMapping.js
module.exports = {
  '#1976d2': 'theme.palette.primary.main',
  '#1565c0': 'theme.palette.primary.dark',
  '#2196f3': 'theme.palette.primary.light',
  // ... add all 20+ colors found in audit
};
```

### 1.4 Create Visual Baselines

```bash
# Take screenshots of all components before migration
npm run test:visual:baseline

# Commit baselines
git add tests/__screenshots__/
git commit -m "test: visual baseline before theme migration"
```

---

## Step 2: Prepare Codemods (Day 2)

### 2.1 Customize Color Mapping

Edit `codemods/replaceSxColors.js`:

```javascript
const colorMap = {
  // Add all colors from audit
  '#1976d2': 'theme.palette.primary.main',
  '#dc2626': 'theme.palette.error.main',
  // ... more from audit-baseline.json
};
```

### 2.2 Customize Spacing Mapping

Review existing `codemods/normalizeSpacing.js`:

```javascript
const spacingMap = {
  '4px': 'spacing(0.5)',
  '8px': 'spacing(1)',
  '16px': 'spacing(2)',
  // Add any custom values found in audit
};
```

### 2.3 Test Codemods on Sample

```bash
# Create test directory with 5 sample components
mkdir -p /tmp/codemod-test
cp src/components/buttons/{Button,IconButton,FAB}.tsx /tmp/codemod-test/

# Run codemod with dry-run
jscodeshift -t codemods/replaceSxColors.js \
  --dry \
  /tmp/codemod-test/*.tsx

# Review output (don't apply yet)
# If looks good, remove --dry flag to apply

# Verify changes
git diff /tmp/codemod-test/
```

### 2.4 Validate Codemod Safety

```bash
# Dry-run on first batch
jscodeshift -t codemods/replaceSxColors.js \
  --parser=babel \
  --dry \
  src/components/buttons/

# Count how many files would change
# Should be: 28 files with sx color props

# If count looks right, proceed
# If count is off, adjust codemod
```

---

## Step 3: Batch 1 - Buttons (Week 1, Mon-Wed)

### 3.1 Run Codemod

```bash
# Navigate to project
cd frontend

# Backup first
git checkout -b migrate/batch-1-buttons

# Apply color migration
jscodeshift -t codemods/replaceSxColors.js \
  --parser=babel \
  src/components/buttons/

# Apply spacing migration
jscodeshift -t codemods/normalizeSpacing.js \
  --parser=babel \
  src/components/buttons/

# Apply CSS cleanup
jscodeshift -t codemods/replaceCssImports.js \
  --parser=babel \
  src/components/buttons/
```

### 3.2 Review Changes

```bash
# See what changed
git diff src/components/buttons/ | head -500

# Check if imports were added
grep -r "useTheme" src/components/buttons/

# Count files modified
git diff --name-only src/components/buttons/ | wc -l
```

**Expected changes:**
- 28-32 files modified
- All hex colors → theme.palette references
- All spacing → theme.spacing()
- CSS imports removed (if any)

### 3.3 Verify No Breakage

```bash
# Run linter
npm run lint -- src/components/buttons/

# Run type checker
npm run type-check -- src/components/buttons/

# Run tests if available
npm run test -- src/components/buttons/

# Build
npm run build
```

**Expected results:**
- ✓ ESLint: 0 errors
- ✓ TypeScript: 0 errors
- ✓ Tests: all pass (if exist)
- ✓ Build: succeeds

### 3.4 Visual Regression Testing

```bash
# Take new screenshots
npm run test:visual:ci -- tests/buttons.spec.ts

# Playwright will compare to baseline and generate report
# Open the report
open playwright-report/index.html

# Review each diff
# - Color changes: approve if expected
# - Layout shifts: investigate
# - Missing styles: investigate

# If all looks good, update baseline
npm run test:visual:update -- tests/buttons.spec.ts

# Commit baseline update
git add tests/__screenshots__/buttons/
git commit -m "test: update button visual baselines"
```

### 3.5 Manual Code Review

```bash
# Ask 2 senior devs to review key files
git diff src/components/buttons/Button.tsx
git diff src/components/buttons/IconButton.tsx

# Check for:
# - Any missed color values
# - Any incorrect spacing mappings
# - Any removed styles that should remain
# - TypeScript compliance
```

### 3.6 Merge Batch 1

```bash
# All checks passed?
# Then merge

git checkout main
git merge migrate/batch-1-buttons

# Deploy to staging
npm run deploy:staging

# Final QA on staging (light + dark mode)
```

---

## Step 4: Batch 2-4 - Forms, Layout, Cards (Week 2)

### 4.1 Monday: Forms

```bash
git checkout -b migrate/batch-2-forms

jscodeshift -t codemods/replaceSxColors.js \
  --parser=babel \
  src/components/form/

jscodeshift -t codemods/normalizeSpacing.js \
  --parser=babel \
  src/components/form/

# Verify
npm run lint -- src/components/form/
npm run test:visual:ci -- tests/form.spec.ts
npm run build

# Merge if good
git checkout main && git merge migrate/batch-2-forms
```

### 4.2 Wednesday: Layout & Cards

```bash
# Same process for layout/
git checkout -b migrate/batch-3-layout
# ... repeat codemod steps ...
git checkout main && git merge migrate/batch-3-layout

# Then for cards/
git checkout -b migrate/batch-4-cards
# ... repeat codemod steps ...
git checkout main && git merge migrate/batch-4-cards
```

**Expected pace:** 1 batch per day once refined

---

## Step 5: Mid-Migration Check (Week 2, Friday)

### 5.1 Comprehensive Audit

```bash
# Audit all migrated components
node scripts/auditThemeUsage.js --output=json > audit-week2.json

# Compare to baseline
# Violations should drop from 287 → ~150
# Check which types remain
```

### 5.2 Metrics

```bash
# Count remaining issues by type
node audit-week2.json | grep -o '"type":"[^"]*"' | sort | uniq -c

# Should see:
# - HARDCODED_HEX: down from 187 → 100
# - INLINE_RGBA: down from 34 → 20
# - INLINE_STYLE_COLOR: down from 45 → 30
# - NON_STANDARD_SPACING: down from 78 → 40
```

### 5.3 Adjust Plan if Needed

```bash
# If conversion rate < 80%:
# - Review problematic patterns
# - Update codemods
# - Re-run on previous batches

# If conversion rate >= 80%:
# - Continue to weeks 3-4
# - Process is working
```

---

## Step 6: Remaining Batches (Week 3-4)

### 6.1 Identify Remaining Components

```bash
# List all non-migrated components
find src/components -name "*.tsx" -o -name "*.jsx" | \
  while read file; do
    if grep -q "#[0-9a-fA-F]" "$file"; then
      echo "$file"
    fi
  done > remaining-to-migrate.txt

# Count by folder
cut -d/ -f3 remaining-to-migrate.txt | sort | uniq -c | sort -rn
```

### 6.2 Batch Remaining in Logical Groups

```bash
# tables/ (50 components)
git checkout -b migrate/batch-5-tables
jscodeshift -t codemods/replaceSxColors.js src/components/tables/
# ... (repeat verification process) ...

# dialogs/ (40 components)
git checkout -b migrate/batch-6-dialogs
# ... same ...

# menus/ (60 components)
git checkout -b migrate/batch-7-menus
# ... same ...

# utils/ (40 components)
git checkout -b migrate/batch-8-utils
# ... same ...
```

---

## Step 7: Final Enforcement & Hardening (Week 4)

### 7.1 Enable ESLint Errors

Edit `.eslintrc.migration.js`:

```javascript
// Change from 'warn' to 'error'
rules: {
  'no-restricted-syntax': [
    'error', // Was 'warn'
    // ... rules ...
  ],
}
```

### 7.2 Update CI Configuration

```yaml
# .github/workflows/eslint.yml
- run: npx eslint src/ --config .eslintrc.migration.js

# This will now fail the build on any violations
```

### 7.3 Final Audit

```bash
# Comprehensive check
node scripts/auditThemeUsage.js --strict

# Should output: AUDIT PASSED
# (If not, identify remaining issues and fix)
```

### 7.4 Performance Verification

```bash
# Check bundle size
npm run build:analyze

# Should show:
# - No increase > 2KB gzipped
# - All theme imports tree-shaken

# Check build time
time npm run build
# Should be < 60 seconds
```

---

## Step 8: Production Deployment (Week 5)

### 8.1 Final Testing

```bash
# Full test suite
npm run test

# Visual regression on production build
npm run test:visual:ci

# Lighthouse check
npm run lighthouse

# Dark mode manual test
# Visit all major components in dark mode
```

### 8.2 Deploy Strategy

```bash
# Deploy to canary first (10% traffic)
npm run deploy:production -- --canary

# Monitor for 2 hours
# - Check error logs
# - Check dark mode usage
# - Check performance metrics

# If all good, full production
npm run deploy:production

# Monitor for 24 hours
# - Any visual regression reports?
# - Any runtime errors?
# - Any performance issues?
```

### 8.3 Post-Launch Checklist

- [ ] 0 new errors in production
- [ ] Visual consistency verified
- [ ] Dark mode working correctly
- [ ] Performance metrics stable
- [ ] User complaints: none
- [ ] Team velocity: maintained
- [ ] Documentation: updated

---

## Troubleshooting

### Issue: Codemod Didn't Change Expected Files

```bash
# Debug: verify parser is correct
jscodeshift -t codemods/replaceSxColors.js \
  --parser=babel \
  --parser-options='ecmaVersion: 2020, sourceType: module, ecmaFeatures: { jsx: true }' \
  --dry \
  src/components/buttons/Button.tsx
```

### Issue: Visual Diffs Not Accepted

```bash
# Review the codemod logic
# Common issue: color mapping is wrong
# Solution: update colorMap in codemod

# Re-run codemod on affected files
# Re-test visually
```

### Issue: ESLint Errors After Codemod

```bash
# Most likely: missing useTheme import
grep "useTheme" src/components/buttons/*.tsx | wc -l

# Add missing imports manually
# Or update codemod to always add import
```

### Issue: Build Failures

```bash
# Check TypeScript errors
npm run type-check 2>&1 | head -20

# Fix broken types
# Usually: theme parameter undefined

# Solution: add useTheme() hook
```

---

## Rollback Procedures

### Rollback Single Batch

```bash
# If batch-5-tables is broken:
git revert <commit-hash-of-batch-5>
git push origin main

# Takes 5 minutes
```

### Rollback Multiple Batches

```bash
# If weeks 2-3 are broken:
git revert <commit-range>

# Or hard reset to before migration
git reset --hard <pre-migration-commit>
git push origin main --force

# Takes 10 minutes
```

### Full Rollback to Original System

```bash
# If entire migration needs undoing:
git log --all --oneline | grep "migration starts"
git reset --hard <pre-migration-commit>

# Restore original files
git restore src/

# Rebuild
npm run build

# Deploy
npm run deploy:production

# Takes 30 minutes
```

---

## Success Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Components migrated | 600+ | ___ |
| Violations remaining | 0 | ___ |
| Visual regressions | 0 | ___ |
| ESLint errors | 0 | ___ |
| Build time increase | < 10% | ___ |
| Bundle size increase | < 2KB | ___ |
| Test coverage | > 95% | ___ |
| Deployment time | < 5 min | ___ |

---

**Last Updated:** 2026-02-28  
**Status:** Ready to Execute  
**Estimated Duration:** 4 weeks  
**Team Allocation:** 3-5 developers
