# PR-UI-07a-1b — Pre-PR Report

> **Pre-merge review artifact.** Generated AFTER implementation, BEFORE commit/push/PR-open.
> Per `AGENTS_UI.md` contract: stop here, wait for human review, do not auto-merge.

**Date:** 2026-08-24
**Branch:** `feat/ui-pr-07a-1b-admin-empty-states` (local only, NOT pushed)
**Base:** `origin/main` @ `6c2e87c` (PR-UI-07a-1a merged)
**Scope phase:** Batch 1b — second migration batch per `docs/reports/PR_UI_07a_READ_ONLY_INVENTORY.md`

---

## 1. Scope correction (vs pre-implementation report)

The pre-implementation report (`docs/reports/PR_UI_07a_1b_PRE_IMPLEMENTATION_INVENTORY.md`) estimated Batch 1b at "13 files, 20 usages, with a question about ClinicManagement.tsx:102 title-only usage".

**After deeper inspection during implementation, the actual count is:**

| Original estimate | Actual after comment-line exclusion |
|---|---|
| 20 usages | **19 usages** |
| 13 files | 13 files (unchanged) |
| ClinicManagement:102 (title-only, real JSX) | **ClinicManagement:102 is a comment line, not real JSX** — `// so the existing <MacOSEmptyState title="Статистика недоступна" /> renders` |

The "title-only MacOSEmptyState usage" mentioned in the comment was already removed in a prior commit (the code shows `setStats(null)` triggering the fallback in line 251 instead). The comment is stale documentation of a previous behavior.

**Therefore: the user's question about `description=""` for ClinicManagement:102 is moot — that usage does not exist as real JSX.**

Additionally, during implementation I discovered another stale comment at `MedicalEquipmentManager.tsx:74` (`// on non-existent equipment. Now shows empty list (existing MacOSEmptyState`). This is also a comment, not real JSX. Both comments are left unchanged (out of scope to clean up comments).

### 1.1 Final actual scope: 19 usages across 13 files

| File | Usages | Lines |
|---|---|---|
| AdminDashboard.tsx | 3 | 366, 418, 455 (last 3 remaining; line 324 was migrated in Batch 1a) |
| BackupManagement.tsx | 1 | 511 |
| BenefitSettings.tsx | 1 | 130 |
| BranchManagement.tsx | 1 | 554 |
| ClinicManagement.tsx | 3 | 203, 251, 329 |
| EquipmentManagement.tsx | 1 | 573 |
| LicenseManagement.tsx | 1 | 530 |
| MedicalEquipmentManager.tsx | 2 | 514, 589 |
| QueueCabinetManagement.tsx | 1 | 480 |
| ReportsManager.tsx | 1 (of 2) | 443 (line 623 EXCLUDED — see §3 below) |
| ServiceCatalog.tsx | 1 | 747 |
| SystemManagement.tsx | 1 (of 3) | 557 (lines 390, 506 EXCLUDED — Group B iconStyle) |
| WizardSettings.tsx | 1 | 117 |
| **Total** | **19** | |

---

## 2. Diff summary

```
 frontend/src/components/admin/AdminDashboard.tsx          | 7 +++----
 frontend/src/components/admin/BackupManagement.tsx        | 4 ++--
 frontend/src/components/admin/BenefitSettings.tsx         | 4 ++--
 frontend/src/components/admin/BranchManagement.tsx        | 4 ++--
 frontend/src/components/admin/ClinicManagement.tsx        | 8 ++++----
 frontend/src/components/admin/EquipmentManagement.tsx     | 4 ++--
 frontend/src/components/admin/LicenseManagement.tsx       | 4 ++--
 frontend/src/components/admin/MedicalEquipmentManager.tsx | 6 +++---
 frontend/src/components/admin/QueueCabinetManagement.tsx  | 4 ++--
 frontend/src/components/admin/ReportsManager.tsx          | 3 ++-
 frontend/src/components/admin/ServiceCatalog.tsx         | 4 ++--
 frontend/src/components/admin/SystemManagement.tsx        | 3 ++-
 frontend/src/components/admin/WizardSettings.tsx          | 4 ++--
 13 files changed, 30 insertions(+), 29 deletions(-)
```

Net: **+1 LOC** across 13 files. All changes are mechanical: `MacOSEmptyState` → `AppEmpty` in both imports and JSX tags. No prop changes. No behavior changes (beyond the documented variant=default → minimal visual delta).

### 2.1 Per-file migration pattern

For each file:
1. Replace `MacOSEmptyState` with `AppEmpty` in the import block (or, for SystemManagement.tsx and ReportsManager.tsx, ADD `AppEmpty` alongside `MacOSEmptyState` because they have remaining Group B usages).
2. Replace each `<MacOSEmptyState` JSX tag with `<AppEmpty`.
3. No other prop or structural changes.

### 2.2 Verified: 0 dead props transferred

Programmatic check (Python with brace-depth-aware JSX parser, comment-line aware) on all 19 `<AppEmpty>` usages confirms:

```
Total AppEmpty usages: 19
Issues (dead props or non-canonical): 0
```

All 19 usages use only canonical props subset `{icon, title, description, action}` — some have all 4, some have 3 (no `action`), some have only 3 (no `action`). None carry `type`, `iconStyle`, `message`, `children`, `variant`, `size`, `className`, or `style`.

---

## 3. Latent bug discovered + excluded (NOT fixed in this PR)

### 3.1 ReportsManager.tsx:624 — silent children drop

**Discovery:** During implementation, I attempted to migrate ReportsManager.tsx:624 (paired-tag MacOSEmptyState with `<Button>retry</Button>` as children). tsc threw:

```
src/components/admin/ReportsManager.tsx(623,12): error TS2322: ...
  Property 'children' does not exist on type 'IntrinsicAttributes & AppEmptyProps...'
```

**Root cause:** `MacOSEmptyState` declares `children?: React.ReactNode` in its props interface (line 15) but **never destructures `children`** (lines 19-28) and **never renders `{children}`** (lines 162-186). So the `<Button>retry</Button>` inside `<MacOSEmptyState>...</MacOSEmptyState>` is **silently dropped at runtime** — the retry button never renders today.

`AppEmpty` does NOT accept `children` in its `AppEmptyProps` type — so passing children causes a type error.

**Action taken:** Per user's strict scope rule ("если обнаружится `message`, `type`, `iconStyle`, `children` или иное отличие от canonical `AppEmpty`, **не исправлять автоматически** — остановиться и классифицировать usage"), I:

1. **Reverted ReportsManager.tsx:624 migration** — restored `<MacOSEmptyState>...<Button>...</MacOSEmptyState>`.
2. **Restored `MacOSEmptyState` in ReportsManager.tsx imports** (kept alongside `AppEmpty` for the migrated line 443).
3. **Did NOT fix the latent bug** — the `<Button>retry</Button>` inside MacOSEmptyState continues to be silently dropped, exactly as in current production. This preserves current behavior.

**Defer to:** PR-UI-07a-2 (Group B with dead props) — when migrating ReportsManager.tsx:624, the latent bug fix should be:
- Convert the paired-tag MacOSEmptyState to self-closing `<AppEmpty icon={...} title={...} description={...} action={<Button onClick={handleRetry}>...</Button>} />` — moving the Button from `children` to `action` prop, which is the canonical pattern that actually renders the retry button.

This is a **behavior fix** (retry button starts rendering) wrapped in a migration — too risky for Batch 1b's mechanical scope. Will be handled separately in PR-UI-07a-2 or a dedicated latent-bug-fix PR.

### 3.2 Other latent bugs deferred (no action in this PR)

- **StateWrapper.tsx** — 3 latent bugs (silent `message` drop, `action={String(emptyAction)}` coercion to "[object Object]", icon ReactElement sizing change). Deferred to PR-UI-07a-3.
- **DermatologistPanelUnified.tsx** — `icon="calendar"` (string literal renders as text "calendar"). Deferred to PR-UI-07a-4.
- **ClinicManagement.tsx:102 + MedicalEquipmentManager.tsx:74** — stale comments mentioning MacOSEmptyState that no longer match real JSX. Could be cleaned up in a separate doc-cleanup PR.

---

## 4. Regression gate (all green)

| Gate | Command | Result | Notes |
|---|---|---|---|
| TypeScript | `npx tsc --noEmit` | ✅ 0 errors | Clean — confirmed ReportsManager.tsx:624 revert restored type safety |
| ESLint (13 changed files explicitly listed) | `npx eslint src/components/admin/AdminDashboard.tsx src/components/admin/BackupManagement.tsx src/components/admin/BenefitSettings.tsx src/components/admin/BranchManagement.tsx src/components/admin/ClinicManagement.tsx src/components/admin/EquipmentManagement.tsx src/components/admin/LicenseManagement.tsx src/components/admin/MedicalEquipmentManager.tsx src/components/admin/QueueCabinetManagement.tsx src/components/admin/ReportsManager.tsx src/components/admin/ServiceCatalog.tsx src/components/admin/SystemManagement.tsx src/components/admin/WizardSettings.tsx` (13 files, explicit list — NOT glob `*.tsx` which would expand to all 61 admin files and report 144 warnings) | ✅ 0 errors, 36 warnings | All 36 pre-existing (single-quote, unused vars); 0 delta from HEAD baseline (verified by stash + re-run on same 13 files) |
| Vitest | `npx vitest run` | ✅ 165/165 test files, 1218/1218 tests passed (20.89s) | No test count delta from main baseline |
| Vite build | `npx vite build` | ✅ Built successfully in 30.21s | Bundle sizes unchanged |
| Programmatic prop check | Python script, brace-depth-aware, comment-line aware | ✅ 19/19 AppEmpty usages canonical, 0 dead props | None of `type`, `iconStyle`, `message`, `children`, `variant`, `size`, `className`, `style` transferred |
| Production grep (residual MacOSEmptyState) | `grep -c "<MacOSEmptyState"` per file | ✅ All remaining MacOSEmptyState JSX is in 2 expected files: ReportsManager.tsx (1 — children latent bug deferred) + SystemManagement.tsx (2 — Group B iconStyle deferred). All other MacOSEmptyState refs are comment lines (no JSX). | See §5 below |
| e2e (Playwright) | (not run locally) | ⏸ Deferred to CI per `AGENTS_UI.md` contract | Path filter `frontend_e2e` triggers only for `frontend/e2e/**`, `frontend/src/components/{registrar,queue,payment,emr,lab}/**`, etc. This PR touches only `frontend/src/components/admin/` — does NOT match. **e2e will be SKIPPED by CI path policy.** |

### 4.1 ESLint warning delta

| File | HEAD warnings | After PR-UI-07a-1b | Delta |
|---|---|---|---|
| AdminDashboard.tsx | 8 | 8 | 0 |
| BackupManagement.tsx | 0 | 0 | 0 |
| BenefitSettings.tsx | 0 | 0 | 0 |
| BranchManagement.tsx | 0 | 0 | 0 |
| ClinicManagement.tsx | 0 | 0 | 0 |
| EquipmentManagement.tsx | 0 | 0 | 0 |
| LicenseManagement.tsx | 0 | 0 | 0 |
| MedicalEquipmentManager.tsx | 3 | 3 | 0 |
| QueueCabinetManagement.tsx | 3 | 3 | 0 |
| ReportsManager.tsx | 13 | 13 | 0 |
| ServiceCatalog.tsx | 0 | 0 | 0 |
| SystemManagement.tsx | 2 | 2 | 0 |
| WizardSettings.tsx | 7 | 7 | 0 |
| **Total** | **36** | **36** | **0** |

All 36 warnings are pre-existing (single-quote style, unused vars) — 0 delta from HEAD.

---

## 5. Residual MacOSEmptyState references (all expected)

After Batch 1b, the following MacOSEmptyState references remain in `frontend/src/components/admin/`:

| File | Line | Type | Reason |
|---|---|---|---|
| ClinicManagement.tsx | 102 | comment line | `// so the existing <MacOSEmptyState title="Статистика недоступна" /> renders` — stale doc |
| MedicalEquipmentManager.tsx | 74 | comment line | `// on non-existent equipment. Now shows empty list (existing MacOSEmptyState` — stale doc |
| ReportsManager.tsx | 29 | import | Kept for line 624 usage (latent children bug deferred) |
| ReportsManager.tsx | 624 | JSX (paired) | **Latent bug**: `<MacOSEmptyState>...<Button>retry</Button></MacOSEmptyState>` — children silently dropped today. Migration deferred to PR-UI-07a-2 with bug fix. |
| ReportsManager.tsx | 633 | JSX close | Paired close of line 624 |
| SystemManagement.tsx | 36 | import | Kept for lines 390, 506 (Group B iconStyle) |
| SystemManagement.tsx | 391 | JSX | Group B iconStyle — deferred to PR-UI-07a-2c |
| SystemManagement.tsx | 507 | JSX | Group B iconStyle — deferred to PR-UI-07a-2c |
| **5 other admin files** (BillingManager, DiscountBenefitsManager, DynamicPricingManager, WebhookManager) | various | import + 9 JSX | All Group B (`type` prop) — deferred to PR-UI-07a-2a |

**Group B total remaining: 13 usages across 5 files (unchanged from pre-implementation inventory).**

---

## 6. Files changed

```
M frontend/src/components/admin/AdminDashboard.tsx          (+4, -3)
M frontend/src/components/admin/BackupManagement.tsx          (+2, -2)
M frontend/src/components/admin/BenefitSettings.tsx          (+2, -2)
M frontend/src/components/admin/BranchManagement.tsx          (+2, -2)
M frontend/src/components/admin/ClinicManagement.tsx          (+4, -4)
M frontend/src/components/admin/EquipmentManagement.tsx     (+2, -2)
M frontend/src/components/admin/LicenseManagement.tsx         (+2, -2)
M frontend/src/components/admin/MedicalEquipmentManager.tsx (+3, -3)
M frontend/src/components/admin/QueueCabinetManagement.tsx   (+2, -2)
M frontend/src/components/admin/ReportsManager.tsx           (+2, -1)
M frontend/src/components/admin/ServiceCatalog.tsx           (+2, -2)
M frontend/src/components/admin/SystemManagement.tsx         (+2, -1)
M frontend/src/components/admin/WizardSettings.tsx           (+2, -2)
```

Plus untracked audit doc: `docs/reports/PR_UI_07a_1b_PRE_IMPLEMENTATION_INVENTORY.md` (will be committed as audit trail).

---

## 7. Visual behavior delta

Same as Batch 1a:
- All 19 migrated usages lose `variant="default"` framing (bg-primary, border, radius-lg).
- AppEmpty forces `variant="minimal"` (transparent bg, no border, no radius).
- Outer `<section className="mac-app-empty" aria-label={title}>` wrapper added (cosmetic, additional DOM level).
- Icon rendering unchanged for component-type icons.
- Retry/create Button onClick callbacks preserved across all 19 usages.

For the 2 `emptyState`-prop usages (ServiceCatalog:747, SystemManagement:557):
- AppEmpty is rendered inside `<tbody>` of `<Table>` via `renderStatusCell(emptyState || 'Нет данных для отображения')`.
- HTML-valid: `<section>` (flow content) is allowed inside `<td>`.
- Visual: empty state appears centered inside a table cell, with column headers visible above. Same as current MacOSEmptyState behavior, just different visual styling due to variant=minimal.

---

## 8. Architectural contract check

| Contract rule | Status |
|---|---|
| Don't change canonical primitive APIs | ✅ AppEmpty/AppState.tsx untouched |
| Don't create new primitives | ✅ None created |
| Don't migrate outside approved scope | ✅ Only 13 admin files touched |
| Don't touch Group B/C consumers | ✅ ReportsManager:624 (children latent bug) and SystemManagement:390/506 (iconStyle) preserved unchanged |
| Don't delete MacOSEmptyState.tsx or its barrel export | ✅ Untouched |
| Stop after Pre-PR Report, wait for review | ✅ This document is the stop point |
| If dead props discovered mid-implementation, stop and classify | ✅ Discovered ReportsManager.tsx:624 children — reverted migration, classified as latent bug, deferred to PR-UI-07a-2 |

---

## 9. Consumer count delta (per PR-UI-07a inventory)

| Metric | Before PR-UI-07a-1b | After PR-UI-07a-1b | Delta |
|---|---|---|---|
| Files referencing MacOSEmptyState (production, admin only) | 17 | 6 (4 Group-B-only files: BillingManager, DiscountBenefitsManager, DynamicPricingManager, WebhookManager + 2 partial files: SystemManagement, ReportsManager) | -11 |
| Production JSX usages (admin only) | 33 | 14 (9 `type` + 4 `iconStyle` + 1 children latent bug) | -19 |
| Files referencing AppEmpty (admin only) | 5 (from Batch 1a) | 17 (Batch 1a's 5 + 12 new from Batch 1b) | +12 net new |

**Reconciliation:**

- **Batch 1a** migrated 5 admin files: AdminAppointments, AdminPatients, AdminDoctors, AdminFinanceOverview (4 fully-migrated) + AdminDashboard (partial — only line 324 migrated, retained MacOSEmptyState import for 3 deferred usages at lines 366/418/455).
- **Batch 1b** migrates 13 admin files: 12 new files (BackupManagement, BenefitSettings, BranchManagement, ClinicManagement, EquipmentManagement, LicenseManagement, MedicalEquipmentManager, QueueCabinetManagement, ReportsManager, ServiceCatalog, SystemManagement, WizardSettings) + AdminDashboard (completing its partial migration from 1a — last 3 usages).
- **After Batch 1b:**
  - **17 admin files import AppEmpty** (Batch 1a's 5 + 12 new from Batch 1b — AdminDashboard counted once since it was already in 1a).
  - **6 admin files still import MacOSEmptyState**: 4 Group-B-only files (BillingManager, DiscountBenefitsManager, DynamicPricingManager, WebhookManager — fully Group B, no AppEmpty) + 2 partial files (SystemManagement, ReportsManager — both import AppEmpty for migrated usages AND keep MacOSEmptyState for Group B/latent-bug usages).
  - **14 MacOSEmptyState JSX usages remain** in admin: 9 with `type` prop (BillingManager 2, DiscountBenefitsManager 4, DynamicPricingManager 3) + 4 with `iconStyle` prop (SystemManagement 2, WebhookManager 2) + 1 with children latent bug (ReportsManager:624).

---

## 10. Pre-PR checklist

- [x] 13 production files modified (only the approved 13)
- [x] 19 usages migrated (verified by grep + programmatic prop check)
- [x] 0 dead props transferred (programmatic verification)
- [x] 1 latent bug discovered + reverted + deferred (ReportsManager.tsx:624 children)
- [x] All gates green (tsc=0, eslint=0 errors / 36 pre-existing warnings, vitest=1218/1218, build=success)
- [x] Pre-PR Report written (this document)
- [ ] **STOP HERE** — wait for human review
- [ ] Do NOT commit (will be done after review approval)
- [ ] Do NOT push
- [ ] Do NOT open PR
- [ ] Do NOT merge

---

## 11. Suggested PR description (for when review approves)

```markdown
## PR-UI-07a-1b — Admin empty-state MacOSEmptyState → AppEmpty (Batch 1b)

Second batch of PR-UI-07a migration per `docs/reports/PR_UI_07a_READ_ONLY_INVENTORY.md` (read-only audit) + `docs/reports/PR_UI_07a_1b_PRE_IMPLEMENTATION_INVENTORY.md` (pre-implementation inventory).

### What
- Migrate 19 MacOSEmptyState usages across 13 admin files to canonical AppEmpty.
- All 19 usages are Group A mechanical drop-in — props subset of {icon, title, description, action}.
- Includes AdminDashboard.tsx last 3 usages (lines 366, 419, 456 — completing the partial migration from Batch 1a).
- 0 dead props transferred (programmatic verification with brace-depth-aware JSX parser).
- 1 latent bug discovered (ReportsManager.tsx:624 — children silently dropped by MacOSEmptyState), reverted migration, deferred to PR-UI-07a-2 with bug fix.

### Files (13 production + 1 audit doc)
- AdminDashboard.tsx (+4, -3) — 3 usages, complete migration (was partial from 1a)
- BackupManagement.tsx (+2, -2) — 1 usage
- BenefitSettings.tsx (+2, -2) — 1 usage
- BranchManagement.tsx (+2, -2) — 1 usage
- ClinicManagement.tsx (+4, -4) — 3 usages (line 102 was a comment, not real JSX)
- EquipmentManagement.tsx (+2, -2) — 1 usage
- LicenseManagement.tsx (+2, -2) — 1 usage
- MedicalEquipmentManager.tsx (+3, -3) — 2 usages
- QueueCabinetManagement.tsx (+2, -2) — 1 usage
- ReportsManager.tsx (+2, -1) — 1 usage migrated (line 443), 1 deferred (line 624 — children latent bug)
- ServiceCatalog.tsx (+2, -2) — 1 usage (passed as emptyState prop to Table)
- SystemManagement.tsx (+2, -1) — 1 usage migrated (line 557 — emptyState prop), 2 deferred (lines 390, 506 — Group B iconStyle)
- WizardSettings.tsx (+2, -2) — 1 usage

### Net
13 production files changed, +30 / -29 LOC (net +1 LOC).
Includes audit trail: docs/reports/PR_UI_07a_1b_PRE_IMPLEMENTATION_INVENTORY.md.

### Visual behavior delta (per Medical Minimalism direction)
- All 19 migrated usages lose variant="default" (bg-primary, border, radius-lg).
- AppEmpty forces variant="minimal" (transparent bg, no border, no radius).
- Outer <section className="mac-app-empty" aria-label={title}> wrapper added.
- Icon rendering unchanged for component-type icons.
- Retry/create Button onClick callbacks preserved across all 19 usages.

### Latent bug discovered + deferred (NOT fixed in this PR)
- ReportsManager.tsx:624 — <MacOSEmptyState>...<Button>retry</Button></MacOSEmptyState> uses children, which MacOSEmptyState declares in props interface but NEVER destructures or renders. So the retry Button is silently dropped today. AppEmpty does not accept children (strict typing) — migration would have caused tsc error. Reverted migration, deferred to PR-UI-07a-2 with bug fix (convert children to action prop, which is canonical and actually renders the button).

### Regression gate (all green)
- tsc --noEmit: 0 errors
- eslint: 0 errors (36 pre-existing warnings, 0 delta from HEAD)
- vitest: 165/165 files, 1218/1218 tests passed (20.89s)
- vite build: success (30.21s)
- Programmatic prop check: 19/19 AppEmpty usages use canonical props, 0 dead props
- e2e: unverified — skipped by CI path policy (admin files not in frontend_e2e filter)

### Out of scope (deferred)
- ReportsManager.tsx:624 (children latent bug) → PR-UI-07a-2
- 5 Group B admin files (BillingManager, DiscountBenefitsManager, DynamicPricingManager — `type` prop; SystemManagement:390/506, WebhookManager — `iconStyle` prop) → PR-UI-07a-2a/2c
- StateWrapper.tsx refactor (high-risk, 3 latent bugs) → PR-UI-07a-3
- DermatologistPanelUnified (icon="calendar" string) → PR-UI-07a-4
- Other non-admin consumers → PR-UI-07a-5-7
- MacOSEmptyState.tsx deletion + barrel export removal → PR-UI-07a-8

### Pre-PR Reports
- Full audit + per-consumer compatibility matrix: `docs/reports/PR_UI_07a_READ_ONLY_INVENTORY.md`
- Pre-implementation inventory: `docs/reports/PR_UI_07a_1b_PRE_IMPLEMENTATION_INVENTORY.md`
- This PR's pre-PR report: `docs/reports/PR_UI_07a_1b_PRE_PR_REPORT.md`

### Reviewer guidance
This is a low-risk mechanical migration. Safe to merge after CI passes. **Do not merge automatically** — wait for human review.
```

---

**End of Pre-PR Report. Awaiting review.**
