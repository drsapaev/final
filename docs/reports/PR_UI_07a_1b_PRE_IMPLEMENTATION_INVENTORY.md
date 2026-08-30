# PR-UI-07a-1b — Pre-Implementation Read-Only Inventory

> **READ-ONLY inventory.** No file changes, no commits, no push, no PR.
> Generated on `main = 6c2e87c` (PR-UI-07a-1a merged).
> Per user's strict scope: only Group A canonical usages, no Group B/C, no `AppEmpty` changes.

---

## 1. Scope reminder (user's strict rule)

- ✅ Group A mechanical migration only
- ✅ 3 remaining `MacOSEmptyState` usages in `AdminDashboard.tsx` (lines 366, 419, 456)
- ✅ Other admin empty-state files from approved inventory
- ❌ NO Group B (dead props `type`/`iconStyle`/`message`/`children`/`variant`/`size`/`className`/`style`)
- ❌ NO Group C (latent bugs in StateWrapper.tsx / DermatologistPanelUnified.tsx)
- ❌ NO `AppEmpty.tsx`/`AppState.tsx`/`MacOSEmptyState.tsx` changes
- ❌ NO `StateWrapper.tsx` / `DermatologistPanelUnified.tsx`
- ❌ NO consumers outside `frontend/src/components/admin/`

---

## 2. Actual count on main = `6c2e87c`

Programmatic classification of all `MacOSEmptyState` JSX usages in `frontend/src/components/admin/`:

| Group | Description | Usages | Files |
|---|---|---|---|
| **A** (canonical: props ⊆ `{icon, title, description, action}`) | Mechanical migration candidates | **20** | **13** |
| B (dead props: `type`) | Excluded — needs prop drop, not mechanical | 9 | 3 (BillingManager, DiscountBenefitsManager, DynamicPricingManager) |
| B (dead props: `iconStyle`) | Excluded — needs prop drop | 4 | 2 (SystemManagement 2 usages, WebhookManager 2 usages) |
| **B total** | | **13** | **5** (with some files having both A and B usages) |
| C (latent bugs / non-canonical pattern) | Excluded | 0 admin files | — |
| **Total admin usages remaining** | | **33** | **17** |

**Discrepancy with the prior audit (PR_UI_07a_READ_ONLY_INVENTORY.md):**
The previous audit estimated Batch 1b at "10 files, ~13 usages". Actual current count after Batch 1a merge: **13 files, 20 usages**. The discrepancy is because:
- The prior audit underestimated Group A scope (it under-counted ClinicManagement.tsx with 4 usages, missed ServiceCatalog.tsx, missed SystemManagement.tsx:557).
- BenefitSettings.tsx and WizardSettings.tsx were actually **not** migrated in Batch 1a (Batch 1a was the 5 files explicitly listed: AdminAppointments, AdminPatients, AdminDoctors, AdminFinanceOverview, AdminDashboard line 324 only). Both BenefitSettings and WizardSettings remain.

---

## 3. Batch 1b candidate list (Group A only)

### 3.1 Per-file matrix (20 usages, 13 files)

| File | Line | Props | Wrapping context | Icon | Title | Description | Action |
|---|---|---|---|---|---|---|---|
| AdminDashboard.tsx | 367 | icon, title, description | bare (inside `div.admin-h-256-radius-...`) | AlertTriangle | `adm_error_load_chart` | `adm_error_load_chart_desc` | — (none) |
| AdminDashboard.tsx | 419 | icon, title, description | wrapped (`div.p-4`) | AlertTriangle | `adm_error_load` | `adm_error_load_recent_actions_desc` | — |
| AdminDashboard.tsx | 456 | icon, title, description | wrapped (`div.p-4`) | AlertTriangle | `adm_error_load` | `adm_error_load_system_notifications_desc` | — |
| BackupManagement.tsx | 511 | icon, title, description, action | bare (after `Skeleton` cards) | HardDrive | `backupEmptyTitle` (var) | `backupEmptyDescription` (var) | `<Button onClick={() => setShowAddForm(true)}>+` create backup |
| BenefitSettings.tsx | 130 | icon, title, description, action | wrapped (`MacOSCard.p-6`) | AlertCircle | `bs_empty_title` ⚠ (i18n mislabel — actually error-state) | `bs_empty_desc` | `<Button onClick={loadSettings} variant="primary">` retry |
| BranchManagement.tsx | 554 | icon, title, description, action | bare (after Skeleton cards) | Building2 | `branchEmptyTitle` (var) | `branchEmptyDescription` (var) | `<Button onClick={() => setShowAddForm(true)}>+` create branch |
| ClinicManagement.tsx | 102 | title only | bare | — | `'Статистика недоступна'` (literal) | — | — |
| ClinicManagement.tsx | 203 | icon, title, description | bare | Activity | `cm_loading_system_status` | `cm_loading_system_status_desc` | — |
| ClinicManagement.tsx | 251 | icon, title, description | bare | BarChart3 | `cm_stats_unavailable` | `cm_stats_unavailable_desc` | — |
| ClinicManagement.tsx | 329 | icon, title, description, action | wrapped | AlertTriangle | `cm_load_data_failed` | `cm_load_data_failed_desc` | `<Button onClick={loadSystemData}>` retry |
| EquipmentManagement.tsx | 573 | icon, title, description, action | bare (after Skeleton cards) | Wrench | `equipmentEmptyTitle` (var) | `equipmentEmptyDescription` (var) | `<Button onClick={() => setShowAddForm(true)}>+` create equipment |
| LicenseManagement.tsx | 530 | icon, title, description, action | bare (after Skeleton cards) | Key | `licenseEmptyTitle` (var) | `licenseEmptyDescription` (var) | `<Button onClick={() => setShowAddForm(true)}>+` create license |
| MedicalEquipmentManager.tsx | 514 | icon, title, description | bare | Stethoscope | `devicesEmptyTitle` (var) | `devicesEmptyDescription` (var) | — |
| MedicalEquipmentManager.tsx | 589 | icon, title, description | bare | WifiOff | `equip_no_available_devices_title` | `equip_no_available_devices_desc` | — |
| QueueCabinetManagement.tsx | 480 | icon, title, description, action | bare (after MacOSCard) | Building2 | `qcm_empty_title` | `qcm_empty_description` | `<Button onClick={() => loadData(appliedFilters)}>` retry |
| ReportsManager.tsx | 443 | icon, title, description | wrapped (`div.admin-flex-center-justify-h-300`) | FileX | `rm_empty_files_title` | `rm_empty_files_desc` | — |
| ReportsManager.tsx | 623 | icon, title, description | wrapped (`MacOSCard.admin-card-p-48-flex-justify-center`) | AlertCircle | `rm_error_title` | `rm_error_desc` | — |
| ServiceCatalog.tsx | 747 | icon, title, description, action | **`emptyState={...}` prop on `<Table>`** | Package | `sc_empty_title` | `sc_empty_desc_filtered/_initial` (conditional) | `<Button onClick={() => setShowAddForm(true)}>+` create service |
| SystemManagement.tsx | 557 | icon, title, description | **`emptyState={...}` prop on `<Table>`** | Database | `sm_no_backups` | `sm_no_backups_desc` | — |
| WizardSettings.tsx | 117 | icon, title, description, action | wrapped (`MacOSCard.admin-p-24`) | AlertCircle | `ws_load_error_title` | `ws_load_error_hint` | `<Button onClick={fetchSettings} variant="primary">` retry |

### 3.2 Counting reconciled

- **Total usages: 20**
- **Total files: 13**

### 3.3 Wrapping context classification

| Context type | Usages | Files |
|---|---|---|
| Bare (MacOSEmptyState is direct return child) | 11 | AdminDashboard:367, BackupManagement, BranchManagement, ClinicManagement:102/203/251, EquipmentManagement, LicenseManagement, MedicalEquipmentManager:514/589, QueueCabinetManagement |
| Wrapped in `<div>` or `<MacOSCard>` | 5 | AdminDashboard:419/456, BenefitSettings, ClinicManagement:329, ReportsManager:443/623, WizardSettings |
| Passed as `emptyState` prop to `<Table>` | 2 | ServiceCatalog:747, SystemManagement:557 |

The 2 `emptyState`-prop usages need attention: `MacOSEmptyState` JSX is passed as a prop value, then rendered by the `Table` component inside `<tbody>{renderStatusCell(emptyState || 'Нет данных...')}</tbody>`. This means the empty state will appear INSIDE a `<tbody>` of a `<table>` — the visual context differs from a bare/wrapped empty state. Migration to AppEmpty preserves the prop pass-through (AppEmpty is just a different component), so the Table wrapping behavior is unchanged. But this is worth flagging — the AppEmpty outer `<section>` wrapper will render inside `<tbody>`, which is structurally valid HTML (a `<section>` inside `<td>` is fine).

---

## 4. Files already migrated in Batch 1a (NOT in Batch 1b)

For verification — these 4 files have 0 `MacOSEmptyState` JSX usages on current main:

- ✅ `AdminAppointments.tsx` (0 usages — migrated)
- ✅ `AdminPatients.tsx` (0 usages — migrated)
- ✅ `AdminDoctors.tsx` (0 usages — migrated)
- ✅ `AdminFinanceOverview.tsx` (0 usages — migrated)

AdminDashboard.tsx is a **partial migration** — 1 usage migrated (line 324 → AppEmpty), 3 remaining usages (lines 367, 419, 456). After Batch 1b, AdminDashboard.tsx will have 0 `MacOSEmptyState` usages, allowing removal of `MacOSEmptyState` from its imports.

---

## 5. Files explicitly EXCLUDED from Batch 1b (Group B — deferred to PR-UI-07a-2a-d)

| File | Line | Props | Excluded because |
|---|---|---|---|
| BillingManager.tsx | 338 | type, title, description, action | `type=invoice` (silently dropped today) |
| BillingManager.tsx | 826 | type, title, description | `type=settings` |
| DiscountBenefitsManager.tsx | 672 | type, title, description, action | `type=discount` |
| DiscountBenefitsManager.tsx | 745 | type, title, description, action | `type=benefit` |
| DiscountBenefitsManager.tsx | 824 | type, title, description, action | `type=loyalty` |
| DiscountBenefitsManager.tsx | 945 | type, title, description | `type=analytics` |
| DynamicPricingManager.tsx | 510 | type, title, description, action | `type=rule` |
| DynamicPricingManager.tsx | 774 | type, title, description, action | `type=package` |
| DynamicPricingManager.tsx | 1023 | type, title, description | `type=analytics` |
| SystemManagement.tsx | 390 | icon, title, description, iconStyle | `iconStyle={{...}}` (silently dropped) |
| SystemManagement.tsx | 506 | icon, title, description, iconStyle | `iconStyle={{...}}` |
| WebhookManager.tsx | 529 | icon, title, description, action, iconStyle | `iconStyle={{...}}` |
| WebhookManager.tsx | 655 | icon, title, description, iconStyle | `iconStyle={{...}}` |

**Total excluded: 13 usages across 5 files.**

These will be migrated in PR-UI-07a-2a (BillingManager, DiscountBenefitsManager, DynamicPricingManager — `type` prop) and PR-UI-07a-2c (SystemManagement, WebhookManager — `iconStyle` prop), with explicit prop removal as part of the migration.

**Note:** 3 of these 5 files (SystemManagement, WebhookManager, DiscountBenefitsManager) have BOTH Group A and Group B usages within the same file. After Batch 1b, they will have ONLY Group B usages remaining (which will be migrated in 2a/2c).

---

## 6. Special notes / risk flags

### 6.1 BenefitSettings.tsx:130 — i18n mislabel

The title key is `admin2.bs_empty_title` but the surrounding code (`if (error && !settings?.updated_at)`) clearly indicates this is an **error-state fallback** (loaded with `AlertCircle` icon + retry Button calling `loadSettings`). The i18n key name is misleading but the behavior is error-state. Migration is mechanical — same pattern as Batch 1a's error-state fallbacks.

### 6.2 ClinicManagement.tsx:102 — title-only usage

Only `title` is passed (no icon, no description, no action). The literal string `'Статистика недоступна'` is used (not even `t(...)` for i18n). After migration to AppEmpty, this becomes `<AppEmpty title="Статистика недоступна" />`. AppEmpty's default `description='Здесь пока нет данных для отображения.'` will kick in, ADDING a description that wasn't there before. **Visual change:** an additional `<p>` element will render with the default description text.

This is a Group A usage (canonical props), but the behavior delta (added default description) is non-trivial. Options:
- (a) Migrate as-is, accept the added description (consistent with AppEmpty's documented contract).
- (b) Pass `description=""` to suppress the default (but AppEmpty's `description?: ReactNode` default is `'Здесь пока нет данных для отображения.'` — passing empty string may or may not suppress rendering depending on `hasDescription` check in MacOSEmptyState).

Looking at MacOSEmptyState source: `hasDescription = Boolean(description)` — empty string is falsy, so `description=""` would suppress rendering. **This is a per-usage decision.** Recommend treating ClinicManagement.tsx:102 as a special case — either migrate with explicit `description=""`, or defer this single usage to a later batch where the description-text decision can be reviewed.

### 6.3 ServiceCatalog.tsx:747 + SystemManagement.tsx:557 — `emptyState` Table prop

Both usages pass `<MacOSEmptyState ... />` as the `emptyState` prop to the `<Table>` component (from `ui/macos/Table.tsx`). The Table component renders this prop via `renderStatusCell(emptyState || 'Нет данных для отображения')` inside a `<tbody>`. After migration to `<AppEmpty .../>` as the emptyState prop value, the same Table rendering path applies — AppEmpty renders inside the `<tbody>` cell.

Visual context: AppEmpty's outer `<section className="mac-app-empty">` wrapper will render inside `<td>`. This is HTML-valid (`<section>` is flow content, allowed in `<td>`). The visual effect: empty state appears centered inside a table cell, with the table's column headers still visible above. Same as current MacOSEmptyState behavior (just different visual styling due to `variant=minimal`).

### 6.4 AdminDashboard.tsx:367 — bare return inside styled div

Line 367 is wrapped inside `<div className="admin-h-256-radius-var-mac-radius-md-d-flex-ai-center-jc-center-bg-dyn" style={{ '--admin-bg0': adminSurface } as CSSProperties}>`. The MacOSEmptyState is rendered inside this fixed-height div with custom background. Migration to AppEmpty preserves the wrapper — AppEmpty renders inside the div, taking the parent's bg/border context. **No special handling needed.**

### 6.5 MedicalEquipmentManager.tsx:589 — `WifiOff` icon

The icon `WifiOff` is a lucide-react component, same as the other icons. No issue. Migration is mechanical.

---

## 7. Visual behavior delta (per-usage expectation)

Same as Batch 1a:
- All 20 migrated usages lose `variant="default"` framing (bg-primary, border, radius-lg).
- AppEmpty forces `variant="minimal"` (transparent bg, no border, no radius).
- Outer `<section className="mac-app-empty" aria-label={title}>` wrapper added.
- Icon rendering unchanged for component-type icons (lucide-react components).
- For ClinicManagement.tsx:102 (title-only usage) — **additional `<p>` element with default description** will render unless `description=""` is explicitly passed.

---

## 8. Recommended scope for Batch 1b PR

**Proposed: 13 files, 20 usages, all Group A canonical.**

However, given the user's strict scope rule ("если обнаружится `message`, `type`, `iconStyle`, `children` или иное отличие от canonical `AppEmpty`, **не исправлять автоматически** — остановиться и классифицировать usage"), I am flagging:

- **ClinicManagement.tsx:102** — title-only usage. AppEmpty will add a default description. This is a behavioral delta beyond the standard `variant=default → minimal` change. **Recommend decision from user: migrate as-is (accept added description) OR migrate with explicit `description=""` OR defer this single usage.**

All other 19 usages are clean mechanical drop-in candidates.

### 8.1 Per-file predicted change count

| File | Usages | Predicted LOC delta |
|---|---|---|
| AdminDashboard.tsx | 3 (migrate) + remove `MacOSEmptyState` from imports (only AppEmpty remains) | ~+3 / -4 (3 usages swapped + import line trimmed) |
| BackupManagement.tsx | 1 + import swap | ~+1 / -1 |
| BenefitSettings.tsx | 1 + import swap | ~+1 / -1 |
| BranchManagement.tsx | 1 + import swap | ~+1 / -1 |
| ClinicManagement.tsx | 4 + import swap | ~+4 / -4 (or +3/-4 if line 102 gets `description=""`) |
| EquipmentManagement.tsx | 1 + import swap | ~+1 / -1 |
| LicenseManagement.tsx | 1 + import swap | ~+1 / -1 |
| MedicalEquipmentManager.tsx | 2 + import swap | ~+2 / -2 |
| QueueCabinetManagement.tsx | 1 + import swap | ~+1 / -1 |
| ReportsManager.tsx | 2 + import swap | ~+2 / -2 |
| ServiceCatalog.tsx | 1 + import swap | ~+1 / -1 |
| SystemManagement.tsx | 1 (line 557 only; lines 390/506 stay Group B) + add `AppEmpty` to existing imports (keep `MacOSEmptyState` for Group B usages) | ~+2 / -1 |
| WizardSettings.tsx | 1 + import swap | ~+1 / -1 |
| **Total** | **20 usages, 13 files** | **~+22 / -21** (net ~+1 LOC) |

---

## 9. Files NOT touched in Batch 1b (confirmed unchanged)

- ✅ `AppState.tsx` — untouched
- ✅ `MacOSEmptyState.tsx` — untouched
- ✅ `macos/index.ts` (barrel) — untouched
- ✅ `Alert.tsx`, `Skeleton.tsx`, `ErrorBoundary.tsx`, `AnimatedLoader.tsx` — untouched
- ✅ `StateWrapper.tsx` — untouched (Group C, PR-UI-07a-3)
- ✅ `DermatologistPanelUnified.tsx` — untouched (Group C, PR-UI-07a-4)
- ✅ All 5 Group B admin files (BillingManager, DiscountBenefitsManager, DynamicPricingManager, SystemManagement usages at 390/506, WebhookManager) — untouched (PR-UI-07a-2a/2c)
- ✅ All non-admin consumers (cardiology, dermatology, doctor, analytics, pages) — untouched (PR-UI-07a-5-7)

---

## 10. Stopping point

**This is a READ-ONLY pre-implementation report.** No code changes have been made. Awaiting user approval before any implementation begins.

### 10.1 Specific question for user

**ClinicManagement.tsx:102** uses `<MacOSEmptyState title="Статистика недоступна" />` (title-only, no description/icon/action). AppEmpty has a default description that will render unless suppressed.

Pick one:
1. **Migrate as-is** — accept the added default description `<p>Здесь пока нет данных для отображения.</p>` (slight visual addition).
2. **Migrate with `description=""`** — explicit suppression (cleanest, matches current visual).
3. **Defer this single usage** — migrate the other 19 usages in Batch 1b, leave ClinicManagement.tsx:102 for a separate micro-PR.

**Recommend option 2** (explicit `description=""`) — preserves exact current visual, no scope creep, no separate micro-PR needed.

### 10.2 Other than that question, scope is ready

All 19 other usages are clean Group A mechanical drop-in candidates, identical pattern to Batch 1a. Same regression gate applies: tsc, eslint, vitest, vite build, programmatic prop check, production grep.

---

**End of pre-implementation report. Awaiting approval.**
