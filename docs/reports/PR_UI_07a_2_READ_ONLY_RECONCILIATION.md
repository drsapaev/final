# PR-UI-07a-2 — Read-Only Cumulative Reconciliation + Pre-Implementation Inventory

> **READ-ONLY.** No file changes, no commits, no push, no PR.
> Generated on `main = ccea6bc` (PR-UI-07a-1b merged).
> Per user instruction: do NOT start PR-UI-07a-2 implementation until reconciliation + inventory complete and approved.

---

## Part A — Cumulative Reconciliation (machine-verified)

### A.1 Baseline SHAs identified

| Stage | Git ref | Description |
|---|---|---|
| Before Batch 1a | `6ce984c` | Parent of PR #2824 merge — last commit before any PR-UI-07a work |
| Batch 1a merged (PR #2824) | `6c2e87c` | Squash commit `fix(ui): PR-UI-07a-1a — migrate admin error states to AppEmpty (#2824)` |
| Before Batch 1b | `6ed4183` | Parent of PR #2825 merge — includes 5 intervening design-token commits (C-3-B.2 through C-3-B.6) |
| Batch 1b merged (PR #2825) | `ccea6bc` | Squash commit `fix(ui): PR-UI-07a-1b — migrate admin empty states to AppEmpty (#2825)` — current main |

### A.2 MacOSEmptyState JSX counts at each stage (admin/ only, comment-line aware)

| # | Stage | Git ref | MacOSEmptyState JSX count |
|---|---|---|---|
| 1 | Before Batch 1a | `6ce984c` | **41** |
| 2 | After Batch 1a / Before Batch 1b (intermediate design-token commits did NOT touch MacOSEmptyState) | `6c2e87c` → `6ed4183` | **32** (unchanged across all 5 design-token commits) |
| 3 | After Batch 1b (current main) | `ccea6bc` | **14** |

### A.3 Migration counts per batch (git diff verified)

| Batch | PR | Diff range | MacOSEmptyState removed | AppEmpty added |
|---|---|---|---|---|
| 1a | #2824 | `6ce984c..6c2e87c` | **9** | **9** |
| 1b | #2825 | `6ed4183..ccea6bc` | **18** | **18** |
| **Total migrated** | | | **27** | **27** |

### A.4 AppEmpty count reconciliation

| Stage | AppEmpty JSX in admin/ |
|---|---|
| Before PR-UI-07a (at `6ce984c`) | **3** (pre-existing in CloudPrintingManager, ServiceAuditHistory, ServiceChangesPreview — unrelated to 07a) |
| After Batch 1a (at `6c2e87c`) | 3 + 9 = **12** |
| After Batch 1b (at `ccea6bc`, current main) | 3 + 9 + 18 = **30** ✓ (verified by direct count) |

### A.5 Arithmetic chain — RECONCILES

```
Before Batch 1a:    41
Batch 1a migrated:  -9
Before Batch 1b:    32  ✓ (41 - 9 = 32)

Before Batch 1b:    32
Batch 1b migrated:  -18
After Batch 1b:     14  ✓ (32 - 18 = 14)
```

### A.6 Investigation: the "32 before Batch 1a / 23 after Batch 1a" discrepancy

**The previous cumulative report was WRONG.** Actual numbers:

| Claim in previous report | Actual (machine-verified) |
|---|---|
| "32 before Batch 1a" | **41** before Batch 1a |
| "23 after Batch 1a" | **32** after Batch 1a |

**Root cause of error:** The previous report conflated "before Batch 1a" with "before Batch 1b" (both design-token intermediate commits preserved the count at 32, but that 32 is the *after-1a* state, not the *before-1a* state). The "23" figure appears to be a pure typo with no derivable source — no combination of 41, 32, 9, 18, 14 produces 23.

**Action:** This was a documentation error in the worklog/verbal report, NOT in any committed audit doc. The audit docs (`PR_UI_07a_1b_PRE_PR_REPORT.md` etc.) correctly stated "32 before / 14 after" for Batch 1b in isolation. No doc fix needed — this reconciliation document is the corrected record.

---

## Part B — PR-UI-07a-2 Pre-Implementation Inventory (14 residual usages)

### B.1 All 14 usages — full prop values + classification

#### Group B-1: `type` prop (9 usages across 3 files)

| # | File:line | type value | title | description | action | Notes |
|---|---|---|---|---|---|---|
| 1 | BillingManager.tsx:338 | `invoice` | `bill_empty_invoices_title` | `bill_empty_invoices_desc` | `<Button onClick={() => setShowCreateInvoice(true)}><Plus/>bill_create_first_inv_btn</Button>` | Empty state for invoices list. type="invoice" appears to be a semantic label, NOT a visual variant. |
| 2 | BillingManager.tsx:826 | `settings` | `bill_settings_title` | `bill_settings_desc` | (none) | Empty state for settings tab. type="settings" is semantic. |
| 3 | DiscountBenefitsManager.tsx:672 | `discount` | `disc_empty_title` | `disc_empty_desc` | `<Button onClick={() => setShowCreateForm(true)}><Plus/>disc_create_first_btn</Button>` | Empty state for discounts sub-tab. type="discount" is semantic. |
| 4 | DiscountBenefitsManager.tsx:745 | `benefit` | `disc_benefits_empty_title` | `disc_benefits_empty_desc` | `<Button onClick={() => setShowCreateForm(true)}><Plus/>disc_create_first_benefit_btn</Button>` | Empty state for benefits sub-tab. type="benefit" is semantic. |
| 5 | DiscountBenefitsManager.tsx:824 | `loyalty` | `disc_loyalty_empty_title` | `disc_loyalty_empty_desc` | `<Button onClick={() => setShowCreateForm(true)}><Plus/>disc_create_first_loyalty_btn</Button>` | Empty state for loyalty programs sub-tab. type="loyalty" is semantic. |
| 6 | DiscountBenefitsManager.tsx:945 | `analytics` | `disc_analytics_empty_title` | `disc_analytics_empty_desc` | (none) | Empty state for analytics sub-tab. type="analytics" is semantic. |
| 7 | DynamicPricingManager.tsx:510 | `rule` | `dp_rules_empty_title` | `dp_rules_empty_desc` | `<Button onClick={() => setShowCreateRule(true)}><Plus/>dp_create_first_rule_btn</Button>` | Empty state for pricing rules sub-tab. type="rule" is semantic. |
| 8 | DynamicPricingManager.tsx:774 | `package` | `dp_packages_empty_title` | `dp_packages_empty_desc` | `<Button onClick={() => setShowCreatePackage(true)}><Plus/>dp_create_first_package_btn</Button>` | Empty state for service packages sub-tab. type="package" is semantic. |
| 9 | DynamicPricingManager.tsx:1023 | `analytics` | `dp_analytics_empty_title` | `dp_analytics_empty_desc` | (none) | Empty state for analytics sub-tab. type="analytics" is semantic. |

**Analysis of `type` prop:**

- `type` is declared in `MacOSEmptyStateProps` (line 14) as `type?: string`
- `type` is **NEVER destructured** in the component body (lines 19-28) — confirmed via source inspection
- `type` is **NEVER rendered** anywhere in the component (lines 162-186) — confirmed
- Therefore `type` is **silently dropped at runtime today** — the values `invoice`, `settings`, `discount`, `benefit`, `loyalty`, `analytics`, `rule`, `package` have **zero visual/semantic effect** in current production

**Critical question for PR-UI-07a-2:** Was `type` intended as a semantic variant that should be preserved?

- **Evidence it's dead:** MacOSEmptyState's actual visual variants are controlled by `variant` prop (`default`/`filled`/`minimal`), not `type`. The `type` prop has no rendering code path.
- **Evidence it might have been intended:** The values are semantic labels (`invoice`, `analytics`, etc.) that suggest the original developer wanted to differentiate empty states by content type. But this intent was never implemented.
- **AppEmpty canonical mapping:** AppEmpty does NOT accept a `type` prop. There is no canonical way to express "this is an invoice empty state" vs "this is a settings empty state" — the differentiation is already expressed via `title` + `description` text (which use distinct i18n keys per type).

**Recommendation:** Drop `type` prop during migration. The semantic intent is already preserved by the distinct `title`/`description` i18n keys. Do NOT attempt to add a `type` prop to AppEmpty — that would re-introduce the parallel-variant anti-pattern.

#### Group B-2: `iconStyle` prop (4 usages across 2 files)

| # | File:line | icon | title | description | action | iconStyle value | Notes |
|---|---|---|---|---|---|---|---|
| 11 | SystemManagement.tsx:391 | `CheckCircle` | `sm_no_active_alerts` | `sm_system_stable` | (none) | `{ width: '48px', height: '48px', color: 'var(--mac-success)' }` | Empty state: no active alerts. iconStyle intended green success icon. |
| 12 | SystemManagement.tsx:507 | `Database` | `sm_no_backups` | `sm_no_backups_desc` | (none) | `{ width: '48px', height: '48px', color: 'var(--mac-text-tertiary)' }` | Empty state: no backups. iconStyle intended tertiary muted icon. |
| 13 | WebhookManager.tsx:529 | `Globe` | `wh_empty_title` | `wh_empty_desc_no_webhooks/_filtered` (conditional) | `<Button onClick={() => setShowCreateModal(true)}>wh_create_btn</Button>` (conditional) | `{ width: '48px', height: '48px', color: 'var(--mac-text-tertiary)' }` | Empty state: no webhooks. iconStyle intended tertiary muted icon. |
| 14 | WebhookManager.tsx:655 | `Activity` | `wh_calls_empty_title` | `wh_calls_empty_desc_with_webhook/_no_webhook` (conditional) | (none) | `{ width: '48px', height: '48px', color: 'var(--mac-text-tertiary)' }` | Empty state: no webhook calls. iconStyle intended tertiary muted icon. |

**Analysis of `iconStyle` prop:**

- `iconStyle` is declared in `MacOSEmptyStateProps` (line 16) as `iconStyle?: CSSProperties`
- BUT line 91 declares a **local variable** `const iconStyle: CSSProperties = { width: currentSize.iconSize, height: currentSize.iconSize, color: 'var(--mac-text-tertiary)', opacity: 0.6 }` — this **shadows** the prop
- The local `iconStyle` is what gets applied to the icon (line 171: `<IconComponent style={iconStyle} />`)
- Therefore the `iconStyle` PROP is **silently dropped** — the icon always renders with the default sizing (48px for `size="md"`) and `var(--mac-text-tertiary)` color at 0.6 opacity

**Critical question for PR-UI-07a-2:** Was `iconStyle` intended to customize icon appearance?

- **Evidence it's dead:** The prop is shadowed by a local variable of the same name. The intent to customize was likely present historically, but the implementation bug means it never worked.
- **Evidence of original intent:** The values are sensible CSS (`width: 48px, height: 48px, color: var(--mac-success)` for success states, `var(--mac-text-tertiary)` for neutral states). The developer wanted:
  - SystemManagement:391 (no alerts) → green CheckCircle (success signal)
  - SystemManagement:507 (no backups) → muted Database (neutral)
  - WebhookManager:529 (no webhooks) → muted Globe (neutral)
  - WebhookManager:655 (no calls) → muted Activity (neutral)
- **Current actual rendering:** ALL 4 icons render at 48px with `var(--mac-text-tertiary)` color at 0.6 opacity (the default). The green success color for CheckCircle is NOT applied — it renders muted gray like the others.

**AppEmpty canonical mapping:**

- AppEmpty does NOT accept `iconStyle` prop
- AppEmpty's `icon` prop accepts `ReactNode | ComponentType<IconWrapperProps>` — when a ReactElement is passed, `normalizeIcon()` wraps it in an `AppEmptyIcon` function component that clones the element and merges styles
- AppEmpty's inner MacOSEmptyState applies its own default `iconStyle` (48px, text-tertiary, 0.6 opacity) — same as current behavior
- To preserve the INTENDED (not actual) green color for CheckCircle, the consumer would need to pass `icon={<CheckCircle style={{ color: 'var(--mac-success)' }} />}` — AppEmpty's normalizeIcon would preserve the original color via style merge

**Recommendation:** For SystemManagement:391 (CheckCircle), consider passing `icon={<CheckCircle style={{ color: 'var(--mac-success)' }} />}` to preserve the original intent (green success icon). For the other 3 (all `var(--mac-text-tertiary)`), the current default rendering is already correct — drop `iconStyle` prop without replacement. This is a **per-usage decision**, not mechanical.

#### Group C: `children` latent bug (1 usage)

| # | File:line | icon | title | description | CHILDREN content | Notes |
|---|---|---|---|---|---|---|
| 10 | ReportsManager.tsx:624 | `AlertCircle` | `rm_error_title` | `rm_error_desc` | `<Button onClick={handleRetry} className="mt-4"><RefreshCw className="w-4 h-4 mr-2"/>{t('admin2.rm_retry_btn')}</Button>` | **LATENT BUG:** Button is passed as children, but MacOSEmptyState never renders children — retry button is silently dropped today. |

**Analysis of `children` prop:**

- `children` is declared in `MacOSEmptyStateProps` (line 15) as `children?: React.ReactNode`
- `children` is **NEVER destructured** in the component body (lines 19-28)
- `children` is **NEVER rendered** anywhere in the component (lines 162-186)
- Therefore the `<Button>retry</Button>` inside `<MacOSEmptyState>...</MacOSEmptyState>` is **silently dropped at runtime** — the retry button NEVER renders in production today

**Critical question for PR-UI-07a-2:** How to migrate while preserving retry semantics?

**Proposed mapping: `children` → `action` prop**

```tsx
// BEFORE (current — broken, retry button never renders):
<MacOSEmptyState
  icon={AlertCircle}
  title={t('admin2.rm_error_title')}
  description={t('admin2.rm_error_desc')}>
    <Button onClick={handleRetry} className="mt-4">
      <RefreshCw className="w-4 h-4 mr-2" />
      {t('admin2.rm_retry_btn')}
    </Button>
</MacOSEmptyState>

// AFTER (canonical — retry button renders via action prop):
<AppEmpty
  icon={AlertCircle}
  title={t('admin2.rm_error_title')}
  description={t('admin2.rm_error_desc')}
  action={
    <Button onClick={handleRetry} className="mt-4">
      <RefreshCw className="w-4 h-4 mr-2" />
      {t('admin2.rm_retry_btn')}
    </Button>
  }
/>
```

**Verification that `action` prop preserves retry semantics:**

| Semantic aspect | Preserved by `action` prop? | Evidence |
|---|---|---|
| Button text (`rm_retry_btn`) | ✅ YES | AppEmpty passes `action` through to MacOSEmptyState (line 209), which renders `{action}` inside `<div style={actionStyle}>{action}</div>` (line 181-183) |
| `onClick={handleRetry}` callback | ✅ YES | Button element is passed as-is to action prop; React renders it with all handlers intact |
| `disabled`/`loading` state | ✅ YES (if added) | Button element accepts standard `disabled` prop; AppEmpty does not interfere |
| Accessibility semantics | ✅ YES | Button renders as `<button>` with native focus/keyboard semantics; AppEmpty's outer `<section aria-label={title}>` provides context |
| Visual layout | ⚠️ MINOR CHANGE | Currently: Button would render inside MacOSEmptyState's children area (but doesn't render at all). After migration: Button renders inside `<div style={{marginTop: '8px'}}>` (MacOSEmptyState's actionStyle). The `className="mt-4"` (16px margin-top) on the Button may stack with the 8px marginTop from actionStyle — visual delta of ~8px additional top margin. **Acceptable** — minor spacing adjustment. |
| Icon (`RefreshCw`) inside Button | ✅ YES | Button children are preserved as-is |

**Behavioral change:** This migration is a **BUG FIX** — the retry button starts rendering (it was silently dropped today). This is a **functional improvement**, not just a visual change. Users will gain the ability to retry after a reports error, which they currently don't have.

**Risk:** Low. The retry button was always intended to render (the code is there, just unreachable). Making it work is the correct behavior.

---

## Part C — Per-usage migration classification

### C.1 Group B-1 (`type` prop) — 9 usages

| Classification | Count | Action |
|---|---|---|
| Dead prop, semantic intent already covered by title/description i18n keys | 9 | Drop `type` prop during migration. Mechanical swap `<MacOSEmptyState type="X" ...>` → `<AppEmpty ...>` (remove `type` prop). |

**All 9 are mechanical drop-in after removing the `type` prop.** No per-usage semantic mapping needed — the i18n keys already differentiate the empty states.

### C.2 Group B-2 (`iconStyle` prop) — 4 usages

| Classification | Count | Action |
|---|---|---|
| Dead prop, default rendering already correct (icon renders at 48px text-tertiary 0.6 opacity — matches the `iconStyle` intent for neutral icons) | 3 | Drop `iconStyle` prop. Mechanical swap. Files: SystemManagement:507, WebhookManager:529, WebhookManager:655. |
| Dead prop, but INTENDED green color was never applied — original developer wanted `var(--mac-success)` for CheckCircle | 1 | Drop `iconStyle` prop. **Optional:** pass `icon={<CheckCircle style={{ color: 'var(--mac-success)' }} />}` to preserve the original intent (green success icon). **Recommendation:** Do NOT add the color override in PR-UI-07a-2 — it would be a behavior change (icon color changes from current gray to green). Defer to a separate UX decision PR. File: SystemManagement:391. |

### C.3 Group C (`children` latent bug) — 1 usage

| Classification | Count | Action |
|---|---|---|
| Latent bug: children never rendered. Migration to `action` prop fixes the bug (retry button starts rendering). | 1 | Convert `<MacOSEmptyState ...>...<Button>...</MacOSEmptyState>` (paired tag with children) to `<AppEmpty ... action={<Button>...</Button>} />` (self-closing with action prop). **This is a behavior fix** — retry button will start rendering. File: ReportsManager:624. |

---

## Part D — Recommended PR-UI-07a-2 scope

### D.1 Proposed split into sub-batches

Given the analysis above, PR-UI-07a-2 can be split into 3 sub-batches:

| Sub-batch | Scope | Usages | Files | Risk |
|---|---|---|---|---|
| **PR-UI-07a-2a** | Group B-1: drop `type` prop (mechanical) | 9 | 3 (BillingManager, DiscountBenefitsManager, DynamicPricingManager) | LOW — dead prop removal, no visual/behavior change |
| **PR-UI-07a-2b** | Group B-2: drop `iconStyle` prop (mechanical, no color override) | 4 | 2 (SystemManagement, WebhookManager) | LOW — dead prop removal, no visual/behavior change |
| **PR-UI-07a-2c** | Group C: ReportsManager:624 children → action (bug fix) | 1 | 1 (ReportsManager) | MEDIUM — behavior fix (retry button starts rendering); visual delta (~8px margin) |

**Total: 14 usages across 5 files (some files appear in multiple sub-batches).**

### D.2 Files touched per sub-batch

| File | Sub-batch(es) | Usages |
|---|---|---|
| BillingManager.tsx | 2a | 2 (lines 338, 826) |
| DiscountBenefitsManager.tsx | 2a | 4 (lines 672, 745, 824, 945) |
| DynamicPricingManager.tsx | 2a | 3 (lines 510, 774, 1023) |
| SystemManagement.tsx | 2b | 2 (lines 391, 507) |
| WebhookManager.tsx | 2b | 2 (lines 529, 655) |
| ReportsManager.tsx | 2c | 1 (line 624) |

### D.3 Why split into sub-batches?

- **2a and 2b are mechanical dead-prop removal** — low risk, can be merged quickly
- **2c is a behavior fix** — should be reviewed separately because it changes runtime behavior (retry button starts rendering)
- Keeping them separate ensures the behavior fix doesn't get lost in a mechanical cleanup PR

### D.4 Post-2c state

After PR-UI-07a-2a/2b/2c, all 14 residual admin usages will be migrated. The remaining MacOSEmptyState usages will be:
- 0 in admin/
- ~5 in non-admin (StateWrapper, DermatologistPanelUnified, cardiology, analytics, doctor) — deferred to PR-UI-07a-3/4/5-7

After all consumers migrated → PR-UI-07a-8 (delete MacOSEmptyState.tsx + barrel export).

---

## Part E — Stopping point

**This is a READ-ONLY reconciliation + inventory.** No code changes, no commits, no push, no PR.

### Summary

1. **Cumulative arithmetic RECONCILES:** 41 (before 1a) - 9 (1a) - 18 (1b) = 14 (current) ✓
2. **Previous report error identified:** "32 before 1a / 23 after 1a" was wrong — actual is "41 before 1a / 32 after 1a". No doc fix needed (error was in verbal report, not in committed audit docs).
3. **14 residual usages fully classified:**
   - 9 `type` prop (Group B-1) — dead prop, mechanical drop
   - 4 `iconStyle` prop (Group B-2) — dead prop, mechanical drop (1 has unfulfilled green-color intent, recommend NOT restoring)
   - 1 `children` (Group C) — latent bug, migrate to `action` prop (behavior fix)
4. **Proposed PR-UI-07a-2 split:** 3 sub-batches (2a: type, 2b: iconStyle, 2c: children bug fix)
5. **No automatic prop deletion** — each dead prop is confirmed dead via source inspection, not assumed

**Awaiting user approval before any implementation begins.**
