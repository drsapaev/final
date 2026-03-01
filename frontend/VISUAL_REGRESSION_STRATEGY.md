# Visual Regression Testing Strategy

## Overview

During theme migration, visual regressions are the highest risk. This document outlines how to detect and prevent them.

---

## Recommended Tools

### Option 1: Chromatic (Storybook Integration)
**Best for:** Component library, existing Storybook setup  
**Cost:** Free tier available, $0-600/month for enterprise  
**Setup time:** 30 minutes

### Option 2: Playwright Visual Comparisons
**Best for:** E2E testing + visual regressions  
**Cost:** Free (open source)  
**Setup time:** 2 hours

### Option 3: Pixelmatch (DIY)
**Best for:** Simple comparison, lightweight  
**Cost:** Free  
**Setup time:** 4 hours

---

## Recommended: Playwright Implementation

### 1. Install Playwright

```bash
npm install --save-dev @playwright/test
npx playwright install
```

### 2. Create Test File

```typescript
// tests/visual-regression.spec.ts
import { test, expect } from '@playwright/test';
import fs from 'fs';

const COMPONENTS = [
  { name: 'Button Primary', url: '/components/button?variant=contained' },
  { name: 'Button Secondary', url: '/components/button?variant=outlined' },
  { name: 'Card Default', url: '/components/card' },
  { name: 'TextField', url: '/components/textfield' },
  { name: 'Dialog', url: '/components/dialog' },
];

test.describe('Visual Regression Suite', () => {
  COMPONENTS.forEach(component => {
    test(`${component.name} - Light Mode`, async ({ page }) => {
      await page.goto(component.url);
      await page.waitForLoadState('networkidle');
      
      // Take screenshot
      await expect(page).toHaveScreenshot(`${component.name}-light.png`, {
        maxDiffPixels: 100, // Allow small differences
      });
    });

    test(`${component.name} - Dark Mode`, async ({ page }) => {
      await page.goto(component.url);
      await page.evaluate(() => {
        document.documentElement.setAttribute('data-theme', 'dark');
      });
      await page.waitForLoadState('networkidle');
      
      await expect(page).toHaveScreenshot(`${component.name}-dark.png`, {
        maxDiffPixels: 100,
      });
    });
  });
});
```

### 3. Update package.json Scripts

```json
{
  "scripts": {
    "test:visual:baseline": "playwright test --project=chromium",
    "test:visual:update": "playwright test --update-snapshots",
    "test:visual:ci": "playwright test --reporter=html"
  }
}
```

### 4. CI Integration

```yaml
# .github/workflows/visual-regression.yml
name: Visual Regression Tests

on:
  pull_request:
    paths:
      - 'src/components/**'
      - 'src/theme/**'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm ci
      - run: npm run test:visual:ci
      - uses: actions/upload-artifact@v3
        if: failure()
        with:
          name: playwright-report
          path: playwright-report/
```

---

## Migration Testing Protocol

### Before Codemod (Baseline)
```bash
# Create baseline snapshots
npm run test:visual:baseline
git add tests/__screenshots__/**
git commit -m "test: visual baseline before migration"
```

### After Codemod (Comparison)
```bash
# Run tests against new code
npm run test:visual:ci

# Playwright will compare and show diffs
# Review diffs in HTML report
open playwright-report/index.html
```

### Acceptable Differences
- Pixel-level anti-aliasing differences (< 10 pixels)
- Transition states
- Hover states (should match, not test)

### Unacceptable Differences
- Color changes
- Layout shifts > 2px
- Missing elements
- Font size changes

---

## Per-Batch Testing

For each codemod batch:

```bash
# 1. Create baseline for this batch
npm run test:visual:baseline -- tests/batch-1-buttons.spec.ts

# 2. Run codemod
jscodeshift -t codemods/replaceSxColors.js src/components/buttons

# 3. Compare
npm run test:visual:ci -- tests/batch-1-buttons.spec.ts

# 4. If diffs exist, review:
# - Open report
# - Approve or reject each diff
# - Document exceptions

# 5. Update baseline if approved
npm run test:visual:update -- tests/batch-1-buttons.spec.ts

# 6. Commit
git add tests/__screenshots__/**
git commit -m "test: update visual baselines for batch 1"
```

---

## Risk Mitigation Checklist

- [ ] Baseline screenshots taken before migration
- [ ] All components tested in light + dark mode
- [ ] CI pipeline fails on visual regressions
- [ ] Visual diffs reviewed by 2+ engineers
- [ ] Approved diffs documented
- [ ] Rollback procedure tested
- [ ] QA sign-off before production deploy

---

## Fallback: Manual Visual Audit

If automated tests are not available:

1. **Before Migration:**
   - Screenshot 50 random components in light + dark mode
   - Store in `/tests/baseline-screenshots/`

2. **After Each Batch:**
   - Screenshot same 50 components
   - Compare manually in Figma or browser
   - Document any differences

3. **Approval:**
   - All screenshots approved by designer
   - Any unexpected diffs investigated
   - Approved screenshots become new baseline

---

**Recommended approach:** Playwright (minimal setup, maximum coverage)  
**Estimated setup time:** 2 hours  
**ROI:** Catch 100% of visual regressions automatically
