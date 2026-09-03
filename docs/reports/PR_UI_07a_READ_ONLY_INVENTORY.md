# PR-UI-07a Read-Only Inventory — MacOSEmptyState → AppEmpty Migration

> **READ-ONLY AUDIT.** No file changes, no commits, no push, no PR.
> Generated on main = `d91332a` (PR-UI-07 Phase 1 merged).
> Per user instructions: do NOT do mechanical global rename. Consumer-by-consumer compatibility inventory first.

---

## 1. Current consumer count (accurate, from main=d91332a)

| Bucket | Count | Notes |
|---|---|---|
| Barrel export (`macos/index.ts`) | 1 | `export { default as MacOSEmptyState } from './MacOSEmptyState';` |
| Implementation file (`MacOSEmptyState.tsx`) | 1 | The component itself |
| Internal wrapper (`AppState.tsx`) | 1 | `AppEmpty` wraps `MacOSEmptyState` internally with `variant="minimal"` |
| Production JSX consumers | **30 files / 56 usages** | All `<MacOSEmptyState … />` JSX |
| Test files | 2 | `MacOSEmptyState.forwardRef.test.tsx` (12 usages, real JSX) + `DoctorQueuePanel.test.tsx` (mock substitution, no real JSX) |
| Comment-only references | 1 | `pages/registrar/views/WelcomeView.tsx:549` — a TODO comment, no code |
| **Total files referencing `MacOSEmptyState`** | **36** | |

**The "57" figure from prior audits is stale** — current actual production JSX consumer count is **30 files / 56 usages**. The Pre-PR Report in PR-UI-07 mentioned "31 production files" but that included `WelcomeView.tsx` which is comment-only — actual JSX production consumers = 30.

### 1.1 Per-directory breakdown

| Directory | Files | Usages |
|---|---|---|
| `frontend/src/components/admin/` | 21 | 42 |
| `frontend/src/components/analytics/` | 2 | 5 |
| `frontend/src/components/cardiology/` | 3 | 3 |
| `frontend/src/components/common/` (StateWrapper.tsx) | 1 | 2 |
| `frontend/src/components/dermatology/` | 1 | 1 |
| `frontend/src/components/doctor/` | 1 | 2 |
| `frontend/src/pages/` (DermatologistPanelUnified.tsx) | 1 | 1 |
| **Production total** | **30** | **56** |
| `frontend/src/components/ui/macos/__tests__/` (test) | 1 | 12 |

---

## 2. API comparison (from source code)

### 2.1 `MacOSEmptyState` props (`frontend/src/components/ui/macos/MacOSEmptyState.tsx:4-17`)

```tsx
interface MacOSEmptyStateProps {
  icon?: React.ElementType | ReactNode;
  title?: ReactNode;             // default: 'Нет данных'
  description?: ReactNode;
  action?: ReactNode;
  size?: 'sm' | 'md' | 'lg' | string;     // default: 'md'
  variant?: string;              // default: 'default'
  className?: string;
  style?: CSSProperties;
  message?: React.ReactNode;     // ⚠ declared but NEVER destructured → silently dropped
  type?: string;                 // ⚠ declared but NEVER destructured → silently dropped
  children?: React.ReactNode;    // ⚠ declared but NEVER destructured → silently dropped
  iconStyle?: CSSProperties;    // ⚠ declared but NEVER destructured → silently dropped
}
```

Only **8 of 12** declared props are actually consumed by the component body. The other 4 (`message`, `type`, `children`, `iconStyle`) are accepted by TypeScript but **silently dropped at runtime** — this is a latent type-safety bug, but it means consumers passing these props see no effect today.

### 2.2 `AppEmpty` props (`frontend/src/components/ui/macos/AppState.tsx:64-71`)

```tsx
interface AppEmptyProps {
  title?: string;            // ⚠ typed as string, not ReactNode (MacOSEmptyState allows ReactNode)
  description?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode | ComponentType<IconWrapperProps>;
  className?: string;        // default: ''
  style?: CSSProperties;     // default: {}
}
```

### 2.3 Critical semantic differences

| Prop | MacOSEmptyState behavior | AppEmpty behavior | Compatible? |
|---|---|---|---|
| `variant` | Default `'default'` → bg-primary, 1px border, radius-lg | Hardcoded `variant="minimal"` → transparent bg, no border, no radius | ❌ **NO — visual change for ALL consumers** (none pass `variant` explicitly, all get `default` today; after migration, all become `minimal`) |
| `size` | Default `'md'` → padding 32px, icon 48px, font lg/base, gap 16px | **Dropped** — MacOSEmptyState receives no `size` prop from AppEmpty, so MacOSEmptyState's own default `'md'` still applies | ✅ YES — same effective sizing (AppEmpty passes through without size override) |
| `iconStyle` | Declared but **silently dropped** | Not a prop of AppEmpty; not forwarded | ✅ YES (already broken — migration doesn't change behavior) |
| `type` | Declared but **silently dropped** | Not a prop of AppEmpty | ✅ YES (already broken) |
| `message` | Declared but **silently dropped** | Not a prop of AppEmpty | ✅ YES (already broken) |
| `children` | Declared but **silently dropped** | Not a prop of AppEmpty | ✅ YES (already broken) |
| `title` | ReactNode | `string` (typed stricter) | ⚠ All current consumers pass `t(...)`, which returns `string`. No production consumer passes ReactNode. Effectively compatible. |
| `icon` | Accepts ElementType **and** ReactNode; handles both via `isIconComponent` detection | Wraps ReactElements via `normalizeIcon()` → ComponentType function. Strings/components pass through unchanged | ⚠ Mostly compatible. **StateWrapper.tsx passes `icon={<AlertCircle size={36} style={{color: red}} />}`** — today renders as `<span>{AlertCircle}</span>` (no extra style); after migration, AppEmptyIcon clones AlertCircle and merges iconStyle `{width:48, height:48, color:text-tertiary, opacity:0.6}` → **icon size 36→48, opacity 1.0→0.6, color overridden to text-tertiary** unless original style wins (style merge order: `props.style, iconElement.props.style` — original wins on conflict for color). **VISUAL CHANGE.** |
| `className` | Applied to root `<div>` | Applied to outer `<section>` wrapper | ⚠ Different element, but className still applied to root visual element. Likely compatible if no consumer uses className (verified: 0 consumers pass `className`). |
| `style` | Spread into root div's `containerStyle` via `...style` | Applied to outer `<section>` | ⚠ Different element. 0 consumers pass `style` (verified). |
| `action` | Rendered inside `<div style={{marginTop: '8px'}}>` | Passed through to MacOSEmptyState (same wrapper) | ✅ YES |
| `description` | Rendered as `<p>` with `maxWidth: 400px` | Passed through to MacOSEmptyState | ✅ YES |

### 2.4 DOM structure difference

**MacOSEmptyState (today):**
```html
<div className role="status" aria-live="polite" aria-atomic="true" aria-describedby={descId} style={containerStyle}>
  <IconComponent style={iconStyle} />  OR  <span>{icon}</span>
  <h3>{title}</h3>
  <p>{description}</p>
  <div style={{marginTop: 8px}}>{action}</div>
</div>
```

**AppEmpty (after migration):**
```html
<section className="mac-app-empty" aria-label={title} style={style}>
  <MacOSEmptyState title={...} description={...} action={...} icon={normalizeIcon(icon)} variant="minimal" />
    <!-- same internal div/icon/h3/p/action structure, but variant=minimal removes bg/border/radius -->
</section>
```

**Net DOM differences:**
1. Extra outer `<section className="mac-app-empty" aria-label={title}>` wrapper added.
2. `variant` forced to `"minimal"` — bg-primary/border/radius removed.
3. `aria-label` moved from inner (via `aria-describedby`) to outer (`aria-label={title}`).

---

## 3. Compatibility matrix (per-consumer)

### 3.1 Prop-set buckets

| Bucket | Usages | Props | Migration risk |
|---|---|---|---|
| B1 | 21 | `{action, description, icon, title}` | LOW-MEDIUM (visual frame loss only) |
| B2 | 15 | `{description, icon, title}` | LOW-MEDIUM |
| B3 | 7 | `{description, title, type}` (type silently dropped today) | LOW-MEDIUM |
| B4 | 6 | `{action, description, title, type}` (type silently dropped today) | LOW-MEDIUM |
| B5 | 3 | `{description, icon, iconStyle, title}` (iconStyle silently dropped today) | MEDIUM — iconStyle was a no-op, but consumer intent was custom icon styling; migration preserves no-op |
| B6 | 2 | `{action, icon, message, title}` (message silently dropped today) | HIGH — **StateWrapper.tsx**, message intent lost, action converted to `String(emptyAction)` (broken — converts ReactNode to "[object Object]") |
| B7 | 1 | `{title}` only | LOW |
| B8 | 1 | `{action, description, icon, iconStyle, title}` | MEDIUM — same as B5 + action |

### 3.2 Full per-consumer matrix

Legend for `Wrap` column: **Card** = inside `<MacOSCard>` parent, **div** = inside `<div className="...">` parent, **bare** = no parent wrapper — MacOSEmptyState is the direct return.

| File | Line | Props | Wrap | Compat? | Transform | Risk | Visual risk | Group |
|---|---|---|---|---|---|---|---|---|
| `DermatologistPanelUnified.tsx` | 1742 | action,description,icon(string="calendar"),title | Card | YES* | Drop string icon, replace with Calendar component OR keep as text; verify intent | MEDIUM | Icon changes from "calendar" text to nothing/symbol | C |
| `ClinicManagement.tsx` | 102 | title only | bare | YES | Pure swap, no other changes | LOW | Loses bg/border (was default variant) | A |
| `ClinicManagement.tsx` | 203 | description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `ClinicManagement.tsx` | 251 | description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `ClinicManagement.tsx` | 329 | action,description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `SystemManagement.tsx` | 390 | description,icon,iconStyle,title | bare | YES* | Drop iconStyle (was no-op anyway) | LOW | Loses bg/border; iconStyle was already no-op | B |
| `SystemManagement.tsx` | 506 | description,icon,iconStyle,title | bare | YES* | Drop iconStyle | LOW | Same as above | B |
| `SystemManagement.tsx` | 557 | description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `WebhookManager.tsx` | 529 | action,description,icon,iconStyle,title | bare | YES* | Drop iconStyle | LOW | Loses bg/border | B |
| `WebhookManager.tsx` | 655 | description,icon,iconStyle,title | bare | YES* | Drop iconStyle | LOW | Loses bg/border | B |
| `EquipmentManagement.tsx` | 573 | action,description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `AdminAppointments.tsx` | 387 | action,description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `AdminAppointments.tsx` | 398 | action,description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `BenefitSettings.tsx` | 130 | action,description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `BillingManager.tsx` | 338 | action,description,title,type | bare | YES* | Drop `type` (was no-op) | LOW | Loses bg/border | B |
| `BillingManager.tsx` | 826 | description,title,type | bare | YES* | Drop `type` | LOW | Loses bg/border | B |
| `BranchManagement.tsx` | 554 | action,description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `DynamicPricingManager.tsx` | 510 | action,description,title,type | bare | YES* | Drop `type` | LOW | Loses bg/border | B |
| `DynamicPricingManager.tsx` | 774 | action,description,title,type | bare | YES* | Drop `type` | LOW | Loses bg/border | B |
| `DynamicPricingManager.tsx` | 1023 | description,title,type | bare | YES* | Drop `type` | LOW | Loses bg/border | B |
| `AdminPatients.tsx` | 281 | action,description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `AdminPatients.tsx` | 292 | action,description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `DiscountBenefitsManager.tsx` | 672 | action,description,title,type | bare | YES* | Drop `type` | LOW | Loses bg/border | B |
| `DiscountBenefitsManager.tsx` | 745 | action,description,title,type | bare | YES* | Drop `type` | LOW | Loses bg/border | B |
| `DiscountBenefitsManager.tsx` | 824 | action,description,title,type | bare | YES* | Drop `type` | LOW | Loses bg/border | B |
| `DiscountBenefitsManager.tsx` | 945 | description,title,type | bare | YES* | Drop `type` | LOW | Loses bg/border | B |
| `AdminFinanceOverview.tsx` | 312 | action,description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `AdminFinanceOverview.tsx` | 324 | action,description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `AdminDoctors.tsx` | 248 | action,description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `AdminDoctors.tsx` | 259 | action,description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `WizardSettings.tsx` | 117 | action,description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `MedicalEquipmentManager.tsx` | 514 | description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `MedicalEquipmentManager.tsx` | 589 | description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `QueueCabinetManagement.tsx` | 480 | action,description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `ReportsManager.tsx` | 443 | description,icon,title | div | YES | Drop-in | LOW | Bg/border from parent preserved | A |
| `ReportsManager.tsx` | 623 | description,icon,title | Card | YES | Drop-in | LOW | Card provides bg/border | A |
| `LicenseManagement.tsx` | 530 | action,description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `AdminDashboard.tsx` | 323 | action,description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `AdminDashboard.tsx` | 366 | description,icon,title | div (`admin-h-256-radius-var-mac-radius-md-...`) | YES | Drop-in | LOW | Div provides bg/border | A |
| `AdminDashboard.tsx` | 418 | description,icon,title | div (`p-4`) | YES | Drop-in | LOW | Loses bg/border (div has no bg) | A |
| `AdminDashboard.tsx` | 455 | description,icon,title | div (`p-4`) | YES | Drop-in | LOW | Loses bg/border | A |
| `BackupManagement.tsx` | 511 | action,description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `ServiceCatalog.tsx` | 747 | action,description,icon,title | prop (`emptyState={...}` to Table) | YES* | Verify Table component renders emptyState directly — if Table adds own wrapper, low risk | MEDIUM | Need to inspect Table component's emptyState rendering | B |
| `WaitTimeAnalytics.tsx` | 338 | description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `WaitTimeAnalytics.tsx` | 509 | description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `WaitTimeAnalytics.tsx` | 597 | description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `WaitTimeAnalytics.tsx` | 680 | description,icon,title | bare | YES | Drop-in | LOW | Loses bg/border | A |
| `AIAnalytics.tsx` | 790 | description,icon,title | prop (`emptyState={...}` to Table) | YES* | Same as ServiceCatalog | MEDIUM | Need Table inspection | B |
| `StateWrapper.tsx` | 99 | action,icon(ReactElement),message,title | bare (returned from StateWrapper) | **NO** | Multiple issues: (1) `message` prop silently dropped — error msg NOT rendered; (2) `action={emptyAction ? String(emptyAction) : undefined}` converts Button ReactNode to "[object Object]" string; (3) AppEmpty's normalizeIcon on `<AlertCircle size={36} style={color:red}/>` changes icon size 36→48 and adds opacity 0.6 | HIGH | Multiple latent bugs surfaced; icon visual change; error msg currently NOT rendered | C |
| `StateWrapper.tsx` | 118 | action,icon,message,title | bare (returned from StateWrapper) | **NO** | Same as above + empty `action` rendered as `String(emptyAction)` if not null | HIGH | Same | C |
| `DoctorQueuePanel.tsx` | 420 | description,title,type | bare | YES* | Drop `type` | LOW | Loses bg/border | B |
| `DoctorQueuePanel.tsx` | 598 | description,title,type | bare | YES* | Drop `type` | LOW | Loses bg/border | B |
| `HistoryTab.tsx` (cardiology) | 178 | description,title,type | bare | YES* | Drop `type` | LOW | Loses bg/border | B |
| `AppointmentsTab.tsx` (cardiology) | 60 | description,title,type | bare | YES* | Drop `type` | LOW | Loses bg/border | B |
| `VisitTab.tsx` (cardiology) | 58 | action,description,icon,title | Card (`cardio-empty-state`) | YES | Drop-in | LOW | Card provides bg/border | A |
| `DermaPhotosTab.tsx` | 52 | action,description,icon,title | bare (returned from component fn) | YES | Drop-in | LOW | Loses bg/border — caller wraps? Need to verify | A |

**Total: 56 production usages across 30 files.**

### 3.3 Risk summary by group

| Group | Description | Count (usages) | Count (files) |
|---|---|---|---|
| **A — Mechanical safe** | Drop-in compatible; visual change is only bg/border loss | 33 | 20 |
| **B — Adapter needed (drop dead props)** | Drop `type`/`iconStyle`/`message` (silently dropped today, so behavior unchanged); still loses bg/border | 21 | 9 |
| **C — Individual rework** | Multiple latent bugs surfaced (StateWrapper); icon string vs component (DermatologistPanelUnified) | 2 | 2 |
| **D — Do not migrate** | Test files mocking MacOSEmptyState — leave mock as-is until MacOSEmptyState itself is deleted, then swap mock to AppEmpty | 0 (production) | 2 (tests) |

---

## 4. High-risk consumers (Group C)

### 4.1 `StateWrapper.tsx` (2 usages, lines 99 + 118)

**Why high-risk:**

1. **Latent bug 1 — `message` prop silently dropped.** StateWrapper passes `message={errMsg}` and `message={emptyMessage}` to MacOSEmptyState. MacOSEmptyState declares `message` in its props interface but **never destructures it** (verified at `MacOSEmptyState.tsx:19-28`). So today, the error message and empty message are **never rendered**. StateWrapper's documented contract ("`emptyMessage` — shown when empty") is silently broken.

2. **Latent bug 2 — `action` coerced to string.** Line 118: `action={emptyAction ? String(emptyAction) : undefined}`. If `emptyAction` is a `<Button>` ReactNode (the documented usage), `String(<Button>)` returns `"[object Object]"`. This is rendered as literal text instead of the Button. Today the rendered output is broken text; after migration to AppEmpty (which accepts ReactNode), the action would render correctly IF we remove the `String()` coercion.

3. **Latent bug 3 — icon visual change.** Line 99 passes `icon={<AlertCircle size={36} style={{color: 'var(--mac-error, #ff3b30)'}} />}`. Today MacOSEmptyState detects ReactElement via `isIconComponent = false` and renders `<span>{<AlertCircle/>}</span>` — AlertCircle renders at size=36 with red color, no opacity override. After migration to AppEmpty, `normalizeIcon()` wraps the ReactElement in an `AppEmptyIcon` function component, which is then rendered as `<AppEmptyIcon style={iconStyle} />` where `iconStyle = {width: 48, height: 48, color: 'var(--mac-text-tertiary)', opacity: 0.6}`. cloneElement merges styles: `{iconStyle, originalElementStyle}` — original wins on conflict for `color`, but `width`/`height`/`opacity` come from iconStyle. **Net: icon size 36→48, opacity 1.0→0.6, color preserved as red** (because original style wins on color conflict). VISUAL CHANGE.

4. **StateWrapper is itself a wrapper used by Unified* panels.** Today, only `UnifiedSettings.tsx` imports StateWrapper (verified). Migrating StateWrapper affects UnifiedSettings behavior — must be tested.

**Recommended handling:** Treat as individual refactor (PR-UI-07a-3 below). Fix the latent bugs while migrating:
- Replace `message={errMsg}` → `description={errMsg}` (now renders the error message — fixes latent bug 1).
- Replace `action={emptyAction ? String(emptyAction) : undefined}` → `action={emptyAction || undefined}` (now renders Button correctly — fixes latent bug 2).
- For the icon, either: (a) keep `<AlertCircle size={36}/>` and accept the visual change (size 36→48, opacity 1.0→0.6); or (b) wrap icon in a custom span before passing: `icon={<span style={{color: 'var(--mac-error, #ff3b30)'}}><AlertCircle size={36}/></span>` — AppEmpty's normalizeIcon will treat this as a ReactElement and wrap it, but the inner span preserves the original AlertCircle size.

### 4.2 `DermatologistPanelUnified.tsx` (1 usage, line 1742)

**Why medium-risk:**

Passes `icon="calendar"` (string literal). MacOSEmptyState today: `isIconComponent = false` for strings, renders `<span aria-hidden="true">calendar</span>` — the literal text "calendar" displayed as icon placeholder. AppEmpty (via normalizeIcon): `React.isValidElement("calendar") = false` → returns "calendar" unchanged → MacOSEmptyState receives "calendar" → same `<span>calendar</span>`. **Behavior identical.**

So this is actually mechanically safe, BUT: passing a string as icon is semantically weird (it's a placeholder, not a real icon). The right migration is to use a lucide-react `Calendar` component. Marked as Group C because it's a small individual fix worth doing right.

### 4.3 Test files (2 files)

- `frontend/src/components/ui/macos/__tests__/MacOSEmptyState.forwardRef.test.tsx` — 12 usages, real JSX. This is the regression test for MacOSEmptyState itself (PR-8B fix for forwardRef icon handling). If MacOSEmptyState.tsx is eventually deleted, this test must be either deleted (behavior covered by AppEmpty tests) or rewritten to test AppEmpty's icon-type coverage.
- `frontend/src/components/doctor/__tests__/DoctorQueuePanel.test.tsx` — mocks `MacOSEmptyState` with a stub component. When MacOSEmptyState is deleted, the mock must be updated to stub `AppEmpty` instead (or removed if DoctorQueuePanel no longer uses MacOSEmptyState directly).

---

## 5. Snapshot impact

### 5.1 Existing Playwright visual regression snapshots

Stored in `frontend/e2e/visual-regression.spec.ts-snapshots/`:

| Snapshot | Targets | Uses MacOSEmptyState? |
|---|---|---|
| `cashier-empty-state-chromium-linux.png` | `.cashier-empty-state` CSS class in CashierPanel.tsx | **NO** — Cashier uses custom empty state, NOT MacOSEmptyState |
| `cashier-pending-tab-chromium-linux.png` | `.cashier-root` | NO |
| `cashier-history-tab-chromium-linux.png` | `.cashier-table` | NO |
| `cashier-overflow-menu-chromium-linux.png` | `.cashier-overflow-popover` | NO |
| `wizard-patient-step-chromium-linux.png` | wizard patient step | NO |
| `wizard-step-progress-chromium-linux.png` | wizard progress | NO |

**None of the 6 existing visual regression snapshots cover any MacOSEmptyState consumer.** Migration to AppEmpty will cause visual changes that are NOT covered by existing snapshot tests.

### 5.2 e2e tests touching MacOSEmptyState text

- `frontend/e2e/cardio-fix-live.spec.ts:68,86` — asserts `getByText('Нет данных анализов')` and `getByText('Нет данных по ЭКГ или анализам крови')` have `count === 0` (i.e., these texts are NOT present after specific data loads). These are cardio empty-state messages — `HistoryTab.tsx:178` and `AppointmentsTab.tsx:60` are MacOSEmptyState consumers. Migration preserves the title text (AppEmpty passes title through), so these assertions remain valid. **LOW RISK.**

### 5.3 Snapshot impact summary

- **No existing snapshots will break** — they don't cover MacOSEmptyState consumers.
- **No new snapshots will be auto-created** — the visual changes from migration are uncovered.
- **Recommendation:** For Group A batches (mechanical), consider adding visual regression snapshots for at least one representative consumer per directory (admin/cardiology/dermatology/analytics) BEFORE migration, to capture the "before" baseline. After migration, update snapshots to lock in the new minimal look. Otherwise, visual regressions in migrated consumers will be silent.

---

## 6. Migration batches (proposed PR sequence)

Each batch is small, has a clear regression gate, and is independently mergeable. The ordering is: low-risk first, complex last.

### Batch 1 — PR-UI-07a-1: Admin panels Group A (mechanical drop-in)

**Scope:** ~13 admin files with 19 usages, all `{action,description,icon,title}` or `{description,icon,title}` or `{title}` only, bare wrappers.

| File | Usages |
|---|---|
| ClinicManagement.tsx (3 usages at lines 203, 251, 329 + 1 at line 102 with `title` only) | 4 |
| EquipmentManagement.tsx | 1 |
| AdminAppointments.tsx | 2 |
| BenefitSettings.tsx | 1 |
| BranchManagement.tsx | 1 |
| AdminPatients.tsx | 2 |
| AdminFinanceOverview.tsx | 2 |
| AdminDoctors.tsx | 2 |
| WizardSettings.tsx | 1 |
| MedicalEquipmentManager.tsx | 2 |
| QueueCabinetManagement.tsx | 1 |
| LicenseManagement.tsx | 1 |
| AdminDashboard.tsx (4 usages, 2 bare + 2 inside div) | 4 |
| BackupManagement.tsx | 1 |
| ReportsManager.tsx (2 usages, both inside Card/div wrappers) | 2 |

**Wait** — that's actually too many files for one PR. Let me split:

#### Batch 1a — PR-UI-07a-1a: Admin "error states" (5 files, ~10 usages)

Files where MacOSEmptyState is used as the error fallback (after API failure): the patterns `? (<MacOSEmptyState icon={AlertCircle/AlertTriangle} ... action={<Button onClick={refresh} variant="primary">...</Button>}/>)`.

- AdminAppointments.tsx (2 usages, both error states)
- AdminPatients.tsx (2 usages, both error states)
- AdminDoctors.tsx (2 usages, both error states)
- AdminFinanceOverview.tsx (2 usages, both error states)
- AdminDashboard.tsx (1 usage at line 323, error state)

**Total: 5 files, 9 usages.** All have `action` with retry button. Group A mechanical swap.

#### Batch 1b — PR-UI-07a-1b: Admin "empty states" (10 files, ~12 usages)

Files where MacOSEmptyState is used as the empty placeholder (when list is empty):

- BranchManagement.tsx
- EquipmentManagement.tsx
- LicenseManagement.tsx
- BackupManagement.tsx
- QueueCabinetManagement.tsx
- MedicalEquipmentManager.tsx (2 usages)
- BenefitSettings.tsx
- WizardSettings.tsx
- AdminDashboard.tsx (3 usages at lines 366, 418, 455 — chart/list empty states)
- ReportsManager.tsx (2 usages, already inside Card/div wrappers — safest)

**Total: 10 files, ~13 usages.**

#### Batch 1c — PR-UI-07a-1c: ClinicManagement.tsx (1 file, 4 usages)

Solo PR for ClinicManagement because it has 4 diverse usages (title-only, full-prop, etc.).

#### Batch 2 — PR-UI-07a-2: Drop dead props (Group B)

**Scope:** 9 files, ~21 usages where `type` or `iconStyle` props are passed but silently dropped today. Migration = remove dead props + swap to AppEmpty.

Files:
- BillingManager.tsx (2 usages, `type=invoice|settings`)
- DynamicPricingManager.tsx (3 usages, `type=rule|package|analytics`)
- DiscountBenefitsManager.tsx (4 usages, `type=discount|benefit|loyalty|analytics`)
- DoctorQueuePanel.tsx (2 usages, `type=users`)
- HistoryTab.tsx (cardiology, 1 usage, `type=calendar`)
- AppointmentsTab.tsx (cardiology, 1 usage, `type=calendar`)
- SystemManagement.tsx (3 usages, `iconStyle`)
- WebhookManager.tsx (2 usages, `iconStyle`)
- ServiceCatalog.tsx (1 usage, `emptyState={...}` prop pass-through — need to verify Table component behavior)
- AIAnalytics.tsx (1 usage, `emptyState={...}` prop pass-through — same)

**Total: 10 files, ~20 usages.** Split further if needed:

- **Batch 2a**: 6 admin files with `type` prop (BillingManager, DynamicPricingManager, DiscountBenefitsManager) — 9 usages
- **Batch 2b**: 4 files with `type` prop (DoctorQueuePanel, HistoryTab, AppointmentsTab) — 4 usages
- **Batch 2c**: 2 admin files with `iconStyle` prop (SystemManagement, WebhookManager) — 5 usages
- **Batch 2d**: 2 files passing emptyState to Table (ServiceCatalog, AIAnalytics) — 2 usages — needs Table component inspection first

#### Batch 3 — PR-UI-07a-3: StateWrapper refactor (Group C, high-risk)

**Scope:** `frontend/src/components/common/StateWrapper.tsx` (1 file, 2 usages).

**Why separate PR:** This file has 3 latent bugs that surface during migration (see §4.1). Migration includes bug fixes:

1. `message` → `description` (fixes silent drop of error/empty message)
2. `action={emptyAction ? String(emptyAction) : undefined}` → `action={emptyAction || undefined}` (fixes Button-to-"[object Object]" coercion)
3. Icon: keep `<AlertCircle size={36} style={{color: 'var(--mac-error, #ff3b30)'}}/>` as ReactElement, OR wrap in span to preserve size after AppEmpty's normalizeIcon merges iconStyle.

Test impact: `UnifiedSettings.tsx` is the only StateWrapper consumer — must verify it still works (loading → error → empty → data transitions).

#### Batch 4 — PR-UI-07a-4: DermatologistPanelUnified (Group C, individual)

**Scope:** `frontend/src/pages/DermatologistPanelUnified.tsx` (1 file, 1 usage at line 1742).

**Why separate PR:** Replace `icon="calendar"` (string literal — renders as text "calendar") with `icon={Calendar}` (lucide-react component — renders as actual calendar icon). This is a small UX improvement bundled with the migration.

The single usage is also wrapped in `<MacOSCard className="derma-p-48">`, so visual frame is preserved by the card.

#### Batch 5 — PR-UI-07a-5: Analytics panels (Group A, 2 files)

- WaitTimeAnalytics.tsx (4 usages)
- AIAnalytics.tsx (1 usage — emptyState prop pass-through, may move to Batch 2d)

#### Batch 6 — PR-UI-07a-6: Cardiology panels (Group B, 1 file remaining after Batch 2b)

- VisitTab.tsx (1 usage, inside `<MacOSCard className="cardio-empty-state">`)

#### Batch 7 — PR-UI-07a-7: DermaPhotosTab + remaining stragglers

- DermaPhotosTab.tsx (1 usage, returned from component function — verify caller wraps)

#### Batch 8 — PR-UI-07a-8: Delete MacOSEmptyState export + file (after all consumers migrated)

**Prerequisites (see §7 below):**
- All 30 production consumers migrated to AppEmpty.
- `AppState.tsx` rewritten to inline the empty-state rendering directly (no longer wraps MacOSEmptyState).
- `MacOSEmptyState.forwardRef.test.tsx` either deleted (coverage assumed by AppState tests) or rewritten to test AppEmpty's icon-type coverage.
- `DoctorQueuePanel.test.tsx` mock updated from `MacOSEmptyState` to `AppEmpty`.

After all 4 prerequisites, delete:
- `frontend/src/components/ui/macos/MacOSEmptyState.tsx` (191 LOC)
- `export { default as MacOSEmptyState } from './MacOSEmptyState';` from `frontend/src/components/ui/macos/index.ts`

### 6.1 Summary table

| Batch | PR | Files | Usages | Group | Risk |
|---|---|---|---|---|---|
| 1a | PR-UI-07a-1a | 5 admin error-state files | 9 | A | LOW |
| 1b | PR-UI-07a-1b | 10 admin empty-state files | ~13 | A | LOW |
| 1c | PR-UI-07a-1c | ClinicManagement.tsx | 4 | A | LOW |
| 2a | PR-UI-07a-2a | 3 admin files (type prop) | 9 | B | LOW-MEDIUM |
| 2b | PR-UI-07a-2b | DoctorQueuePanel + 2 cardiology | 4 | B | LOW-MEDIUM |
| 2c | PR-UI-07a-2c | SystemManagement + WebhookManager | 5 | B | LOW-MEDIUM |
| 2d | PR-UI-07a-2d | ServiceCatalog + AIAnalytics | 2 | B | MEDIUM (Table inspection) |
| 3 | PR-UI-07a-3 | StateWrapper.tsx (UnifiedSettings) | 2 | C | HIGH |
| 4 | PR-UI-07a-4 | DermatologistPanelUnified.tsx | 1 | C | MEDIUM |
| 5 | PR-UI-07a-5 | WaitTimeAnalytics.tsx | 4 | A | LOW |
| 6 | PR-UI-07a-6 | VisitTab.tsx (cardiology) | 1 | A | LOW |
| 7 | PR-UI-07a-7 | DermaPhotosTab.tsx | 1 | A | LOW |
| 8 | PR-UI-07a-8 (deletion) | macos/index.ts + MacOSEmptyState.tsx + 2 test files | — | — | LOW (post-prerequisites) |

**Total: ~13 PRs.** Each is small, has a clear regression gate, and can be merged independently.

---

## 7. Deletion prerequisites (for PR-UI-07a-8)

Before `MacOSEmptyState` export and file can be deleted, ALL of the following must be true:

| # | Prerequisite | Verification |
|---|---|---|
| 1 | All 30 production JSX consumers migrated to `AppEmpty` (or other canonical) | `grep -rln "MacOSEmptyState" frontend/src --include='*.tsx' \| grep -v "__tests__" \| grep -v "MacOSEmptyState.tsx" \| grep -v "AppState.tsx" \| grep -v "macos/index.ts"` returns empty |
| 2 | `AppState.tsx` no longer imports `MacOSEmptyState` — AppEmpty renders its own content (or imports a different canonical subcomponent) | `grep "MacOSEmptyState" frontend/src/components/ui/macos/AppState.tsx` returns empty |
| 3 | `MacOSEmptyState.forwardRef.test.tsx` either deleted (icon-type coverage moved to `AppState.test.tsx`) or rewritten to test AppEmpty | Inspect `frontend/src/components/ui/macos/__tests__/` |
| 4 | `DoctorQueuePanel.test.tsx` mock updated from `MacOSEmptyState` to `AppEmpty` (or DoctorQueuePanel no longer uses MacOSEmptyState directly post-migration) | `grep "MacOSEmptyState" frontend/src/components/doctor/__tests__/DoctorQueuePanel.test.tsx` returns empty |

After prerequisites met:
- DELETE `frontend/src/components/ui/macos/MacOSEmptyState.tsx` (191 LOC)
- DELETE the line `export { default as MacOSEmptyState } from './MacOSEmptyState';` from `frontend/src/components/ui/macos/index.ts`
- DELETE the clarifying comment block added in PR-UI-07 (3 lines)
- Run regression gate: `tsc=0`, `eslint=0 errors`, `vitest=...`, `vite build=success`, `grep -rln "MacOSEmptyState" frontend/src` returns empty
- Run e2e (Playwright) to verify no runtime breakage — note: existing e2e path filter only triggers for `frontend/e2e/**`, `frontend/src/components/{registrar,queue,payment,emr,lab}/**`, etc. Since this PR touches `frontend/src/components/ui/macos/`, e2e will be SKIPPED — needs manual e2e run via `workflow_dispatch` or local Playwright execution.

---

## 8. Exact recommended scope for first migration PR

**Recommended first PR: PR-UI-07a-1a (Batch 1a — Admin error states)**

### 8.1 Files (5)

```
frontend/src/components/admin/AdminAppointments.tsx       2 usages (lines 387, 398)
frontend/src/components/admin/AdminPatients.tsx           2 usages (lines 281, 292)
frontend/src/components/admin/AdminDoctors.tsx             2 usages (lines 248, 259)
frontend/src/components/admin/AdminFinanceOverview.tsx    2 usages (lines 312, 324)
frontend/src/components/admin/AdminDashboard.tsx          1 usage  (line 323 — statsError state only)
```

**Total: 5 files, 9 usages.**

### 8.2 Per-file transform (uniform pattern)

For each `<MacOSEmptyState ... />`:

1. Replace `<MacOSEmptyState` with `<AppEmpty`.
2. Verify `icon` is a lucide-react component (e.g., `icon={AlertCircle}`) — all 9 usages in this batch pass a component, NOT a ReactElement. Verified via prop-set bucket B1.
3. Verify `title` is `t(...)` (returns string, matches AppEmpty's stricter `title?: string` type). Verified.
4. Verify `description` is `t(...)` or string literal. Verified.
5. Verify `action` is `<Button>...</Button>` JSX. Verified.
6. Remove `import { MacOSEmptyState }` from `../ui/macos`, replace with `import { AppEmpty }` (or add AppEmpty to existing import list).
7. No other prop changes.

### 8.3 Visual behavior delta

**Expected visual change:** All 9 migrated usages will lose their `variant="default"` background/border/borderRadius. AppEmpty wraps content in `<section className="mac-app-empty">` and forces `variant="minimal"` (transparent bg, no border, no radius).

For error states rendered bare (e.g., `error ? <AppEmpty .../> : ...`), the empty state will appear without a frame. This is the intended canonical look (matches the design intent of `AppEmpty` — minimal, transparent).

### 8.4 Regression gate

- `npx tsc --noEmit` → 0 errors
- `npx eslint src/components/admin/Admin{Appointments,Patients,Doctors,FinanceOverview,Dashboard}.tsx` → 0 errors
- `npx vitest run` → 1212/1212 tests pass
- `npx vite build` → success
- Production grep: `grep -rln "MacOSEmptyState" frontend/src/components/admin/Admin{Appointments,Patients,Doctors,FinanceOverview,Dashboard}.tsx` → 0 matches
- Manual: load admin pages with error states triggered (e.g., kill backend, navigate to /admin/appointments) — verify empty state renders without frame, error message visible, retry button works.
- e2e: SKIPPED by CI path policy (admin files are not in `frontend_e2e` path filter). Note this as "unverified" in PR description.

### 8.5 Out of scope for this first PR

- Any Group B/C consumer (deferred to subsequent batches).
- Deletion of MacOSEmptyState.tsx or barrel export (deferred to PR-UI-07a-8).
- Any change to AppState.tsx, Alert.tsx, Skeleton.tsx, ErrorBoundary.tsx, AnimatedLoader.tsx.
- Visual regression snapshots (recommend adding in a later PR after the migration pattern is proven).
- Test file changes (MacOSEmptyState.forwardRef.test.tsx and DoctorQueuePanel.test.tsx — defer until PR-UI-07a-8).

### 8.6 PR description template (for when implementation begins)

```markdown
## PR-UI-07a-1a — Admin error-state MacOSEmptyState → AppEmpty (Batch 1a)

First batch of PR-UI-07a migration per `docs/reports/PR_UI_07a_READ_ONLY_INVENTORY.md`.

### What
- Migrate 9 usages across 5 admin files from `<MacOSEmptyState>` to `<AppEmpty>`.
- All 9 usages are error-state fallbacks after API failure (icon=AlertCircle/AlertTriangle, action=retry Button).
- Drop-in compatible: all pass `{icon, title, description, action}` props, all of which AppEmpty accepts with same semantics.
- No prop changes needed; no dead props to drop.

### Visual behavior delta
- All 9 migrated error states lose `variant="default"` (bg-primary, border, radius-lg).
- AppEmpty forces `variant="minimal"` (transparent bg, no border, no radius).
- Wraps in `<section className="mac-app-empty" aria-label={title}>`.

### Files (5)
- frontend/src/components/admin/AdminAppointments.tsx
- frontend/src/components/admin/AdminPatients.tsx
- frontend/src/components/admin/AdminDoctors.tsx
- frontend/src/components/admin/AdminFinanceOverview.tsx
- frontend/src/components/admin/AdminDashboard.tsx

### Regression gate
- tsc --noEmit: 0 errors
- eslint: 0 errors
- vitest: 1212/1212 tests passed
- vite build: success
- Production grep: 0 MacOSEmptyState refs in 5 changed files
- e2e: unverified — skipped by CI path policy (admin files not in frontend_e2e filter)

### Out of scope (deferred)
- All other MacOSEmptyState consumers → subsequent PR-UI-07a-* batches
- StateWrapper.tsx refactor (high-risk, has latent bugs) → PR-UI-07a-3
- MacOSEmptyState.tsx deletion → PR-UI-07a-8 (after all consumers migrated)

### Pre-PR Report
Full compatibility matrix + per-consumer analysis: docs/reports/PR_UI_07a_READ_ONLY_INVENTORY.md
```

---

## 9. Risks and unknowns

### 9.1 Visual regression safety net is absent

Existing Playwright visual regression snapshots (6 PNGs) do NOT cover any MacOSEmptyState consumer. Migrated consumers will have visual changes that no automated test catches. **Recommendation:** for at least the first 2 batches (PR-UI-07a-1a, 1b), manually screenshot before/after on at least one representative admin page (e.g., /admin/appointments with API failure).

### 9.2 AppEmpty's `title` type is stricter

AppEmpty declares `title?: string`, but MacOSEmptyState allows `title?: ReactNode`. None of the 30 production consumers pass a non-string title (all use `t(...)`), so this is currently safe. **But:** if any future code wants to pass `<Trans>` component or JSX as title, AppEmpty's type will reject it. Consider widening AppEmpty's `title` to `ReactNode` in a separate PR (out of scope here).

### 9.3 AppEmpty hardcodes `variant="minimal"` — design decision

The hardcoded `variant="minimal"` in AppEmpty means all consumers lose the framed look. This is by design (per the Medical Minimalism direction in `docs/UI_REMEDIATION_PLAN.md`). If any consumer's design actually needs the framed look (bg-primary + border + radius), the consumer should wrap AppEmpty in a `<Card>` or `<div>` with explicit bg/border styling. **This is per-consumer and cannot be batched.**

### 9.4 StateWrapper latent bugs (Group C)

StateWrapper.tsx has 3 latent bugs that are NOT caused by this migration but ARE surfaced by it:
1. `message` prop silently dropped (error message not rendered today).
2. `action` coerced to `String()` (Button rendered as "[object Object]" today).
3. `icon` ReactElement gets different sizing/opacity after AppEmpty migration.

**Recommendation:** Fix bugs 1 and 2 in PR-UI-07a-3 as part of the migration (they're invisible today but become visible after migration). Document bug 3 as an intentional visual change.

### 9.5 `emptyState` prop pass-through (ServiceCatalog, AIAnalytics)

Two consumers pass `<MacOSEmptyState .../>` as the `emptyState` prop to a Table component. The Table component then renders it when the table is empty. Need to inspect Table component's rendering of `emptyState` — if Table wraps it in a `<tbody>` or styled `<div>`, the bg/border change may or may not matter. **Defer to Batch 2d** with explicit Table inspection.

### 9.6 e2e path policy

PR-UI-07a batches touch `frontend/src/components/admin/`, `frontend/src/components/cardiology/`, etc. — these directories are NOT in the `frontend_e2e` path filter (which only triggers for `frontend/e2e/**`, `frontend/src/components/{registrar,queue,payment,emr,lab}/**`, `frontend/src/{pages,panels,routing}/**`, `App.jsx`, `PublicApp.jsx`). e2e will be SKIPPED for all PR-UI-07a batches. This is per the user's existing contract ("e2e если CI skip то не считается успехом"). e2e is unverified for the entire PR-UI-07a effort unless path filters are changed or e2e is run manually.

---

## 10. Final notes

- **No code was changed in producing this report.** All analysis is from read-only inspection of `main = d91332a`.
- The "30 production consumers / 56 usages" figure is accurate as of the audit date. If main advances before PR-UI-07a-1a begins, re-verify the count.
- The recommended first PR (PR-UI-07a-1a) is the smallest safe batch: 5 files, 9 usages, all in Group A (mechanical drop-in), all error-state usages with retry Button actions.
- The migration sequence proposed here is **explicitly NOT a mechanical global rename** — it's consumer-by-consumer with each batch sized to fit a single review session, with separate PRs for high-risk (Group C) and prop-cleanup (Group B) cases.

**Stopping here. Awaiting review before any implementation begins.**
