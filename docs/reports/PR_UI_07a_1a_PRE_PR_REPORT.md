# PR-UI-07a-1a — Pre-PR Report

> **Pre-merge review artifact.** Generated AFTER implementation, BEFORE commit/push/PR-open.
> Per `AGENTS_UI.md` contract: stop here, wait for human review, do not auto-merge.

**Date:** 2026-08-24
**Branch:** `feat/ui-pr-07a-1a-admin-error-states` (local only, NOT pushed)
**Base:** `origin/main` @ `da73064` (chore(tooling): absorb PR-UI-07 improvements into ui-baseline)
**Scope phase:** Batch 1a — first migration batch from `docs/reports/PR_UI_07a_READ_ONLY_INVENTORY.md`

---

## 1. Scope (user-approved, strict)

### 1.1 Approved: 5 admin files, 9 JSX usages, Group A error-state fallbacks

| File | Usages | Line numbers |
|---|---|---|
| `frontend/src/components/admin/AdminAppointments.tsx` | 2 | 387, 398 |
| `frontend/src/components/admin/AdminPatients.tsx` | 2 | 281, 292 |
| `frontend/src/components/admin/AdminDoctors.tsx` | 2 | 248, 259 |
| `frontend/src/components/admin/AdminFinanceOverview.tsx` | 2 | 312, 324 |
| `frontend/src/components/admin/AdminDashboard.tsx` | 1 (of 4 total in file) | 324 (lines 366, 419, 456 deferred to Batch 1b) |
| **Total** | **9** | |

### 1.2 Explicit forbidden actions (user's hard scope rules)

| ❌ Not done | Verified |
|---|---|
| Change `AppEmpty`/`AppState.tsx` | ✅ Untouched |
| Change `MacOSEmptyState.tsx` | ✅ Untouched |
| Change canonical `AppEmpty` API | ✅ Untouched |
| Fix StateWrapper latent bugs | ✅ Untouched (deferred to PR-UI-07a-3) |
| Touch `DermatologistPanelUnified.tsx` | ✅ Untouched (deferred to PR-UI-07a-4) |
| Migrate other consumers (Groups B/C/other Group A) | ✅ Untouched |
| Delete `MacOSEmptyState` | ✅ Untouched (deferred to PR-UI-07a-8) |
| Add new UI primitives or adapters | ✅ None created |
| Global rename/search-replace outside 5 allowed files | ✅ Only 5 files modified |
| Touch `Alert.tsx`, `Skeleton.tsx`, `ErrorBoundary.tsx`, `AnimatedLoader.tsx` | ✅ Untouched |

### 1.3 AdminDashboard.tsx partial migration

AdminDashboard.tsx has 4 total MacOSEmptyState usages. Only line 324 (statsError with retry Button action) is in scope for Batch 1a. The other 3 usages (lines 366, 419, 456 — chart/list empty states without action prop) are deferred to Batch 1b (PR-UI-07a-1b).

The file's import block now contains BOTH `AppEmpty` (for migrated usage) AND `MacOSEmptyState` (for the 3 unmigrated usages). This is intentional and correct — `MacOSEmptyState` cannot be removed from imports until all 4 usages are migrated.

---

## 2. Diff summary

```
 frontend/src/components/admin/AdminAppointments.tsx    | 6 +++---
 frontend/src/components/admin/AdminDashboard.tsx       | 3 ++-
 frontend/src/components/admin/AdminDoctors.tsx         | 6 +++---
 frontend/src/components/admin/AdminFinanceOverview.tsx | 6 +++---
 frontend/src/components/admin/AdminPatients.tsx        | 6 +++---
 5 files changed, 14 insertions(+), 13 deletions(-)
```

Net: **+1 LOC** across 5 files. All changes are mechanical: `MacOSEmptyState` → `AppEmpty` in both imports and JSX tags. No prop changes. No behavior changes.

### 2.1 Per-usage transform pattern (uniform across all 9 usages)

Each `<MacOSEmptyState ... />` JSX tag became `<AppEmpty ... />` with identical props:

| Prop | Before (MacOSEmptyState) | After (AppEmpty) | Compatible? |
|---|---|---|---|
| `icon` | lucide-react component (RefreshCw/Calendar/Users/Stethoscope/CreditCard/AlertCircle) | Same component | ✅ AppEmpty accepts `ReactNode \| ComponentType` |
| `title` | `t('...')` returning string | Same string | ✅ AppEmpty accepts `title?: string` |
| `description` | `t('...')` or string expression | Same ReactNode | ✅ AppEmpty accepts `description?: ReactNode` |
| `action` | `<Button onClick={...}>...</Button>` JSX | Same ReactNode | ✅ AppEmpty accepts `action?: ReactNode` |

### 2.2 Verified: 0 dead props transferred

Programmatic check (Python with brace-depth-aware JSX parser) on all 9 `<AppEmpty>` usages confirms:

```
AdminAppointments.tsx:387   props=['icon', 'title', 'description', 'action']   OK
AdminAppointments.tsx:398   props=['icon', 'title', 'description', 'action']   OK
AdminPatients.tsx:281       props=['icon', 'title', 'description', 'action']   OK
AdminPatients.tsx:292       props=['icon', 'title', 'description', 'action']   OK
AdminDoctors.tsx:248        props=['icon', 'title', 'description', 'action']   OK
AdminDoctors.tsx:259        props=['icon', 'title', 'description', 'action']   OK
AdminFinanceOverview.tsx:312 props=['icon', 'title', 'description', 'action']  OK
AdminFinanceOverview.tsx:324 props=['icon', 'title', 'description', 'action']  OK
AdminDashboard.tsx:324      props=['icon', 'title', 'description', 'action']   OK
```

None of the silently-dropped MacOSEmptyState props (`type`, `iconStyle`, `message`, `children`, `variant`, `size`, `className`, `style`) were transferred to AppEmpty.

### 2.3 Per-usage semantic verification

For each of the 9 migrated usages, the table below verifies that the title/description/action/icon mapping preserves the original intent:

| File:line | icon | title | description | action | Severity semantics |
|---|---|---|---|---|---|
| `AdminAppointments.tsx:387` | `RefreshCw` | `admin2.appt_load_error_title` | `admin2.appt_load_error_desc` | `<Button onClick={refresh} startIcon={<RefreshCw/>}>appt_refresh_btn</Button>` | Error-state (after `error ?`) — retry on click ✅ |
| `AdminAppointments.tsx:398` | `Calendar` | `admin2.appt_empty_title` | `admin2.appt_empty_*_desc` (filtered/unfiltered) | `<Button onClick={handleCreateAppointment} startIcon={<Plus/>}>appt_create_first_btn</Button>` | Empty-state (after `appointments.length === 0`) — create first ✅ |
| `AdminPatients.tsx:281` | `RefreshCw` | `admin2.ap_load_error_title` | `admin2.ap_load_error_desc` | `<Button onClick={refresh}>ap_refresh_btn</Button>` | Error-state ✅ |
| `AdminPatients.tsx:292` | `Users` | `admin2.ap_empty_title` | `admin2.ap_empty_desc_*` | `<Button onClick={handleCreatePatient}>ap_add_first_patient_btn</Button>` | Empty-state ✅ |
| `AdminDoctors.tsx:248` | `RefreshCw` | `admin2.ad_error_load_title` | `admin2.ad_error_load_description` | `<Button onClick={refresh}>ad_refresh</Button>` | Error-state ✅ |
| `AdminDoctors.tsx:259` | `Stethoscope` | `admin2.ad_empty_title` | `admin2.ad_empty_filters/no_doctors` | `<Button onClick={handleCreateDoctor}>ad_add_first_doctor</Button>` | Empty-state ✅ |
| `AdminFinanceOverview.tsx:312` | `CreditCard` | `admin2.fo_error_title` | `admin2.fo_error_desc` | `<Button onClick={refreshFinance}>fo_refresh_btn</Button>` | Error-state ✅ |
| `AdminFinanceOverview.tsx:324` | `CreditCard` | `admin2.fo_empty_title` | `admin2.fo_empty_desc(_filtered)` | `<Button onClick={handleCreateTransaction}>fo_add_first_transaction</Button>` | Empty-state ✅ |
| `AdminDashboard.tsx:324` | `AlertCircle` | `admin2.adm_error_load_stats` | `admin2.adm_error_load_stats_desc` | `<Button onClick={refreshStats} variant="primary">adm_retry</Button>` | Error-state (statsError) ✅ |

All 9 usages preserve:
- ✅ Retry Button `onClick` callback wired to the original `refresh`/`refreshStats`/`refreshFinance`/`handleCreate*` handler.
- ✅ Icon semantically matches state (RefreshCw for error-retry, Calendar/Users/Stethoscope/CreditCard for empty-create, AlertCircle for stats error).
- ✅ Title/description text keys unchanged (preserves i18n behavior).
- ✅ Button variant preserved where present (`variant="primary"` on AdminDashboard:324, others use default).

---

## 3. Visual behavior delta

**Expected visual change:** All 9 migrated usages will lose their `variant="default"` framing.

| Before (MacOSEmptyState default) | After (AppEmpty, variant="minimal" hardcoded) |
|---|---|
| `<div>` with `background: var(--mac-bg-primary)`, `border: 1px solid var(--mac-border)`, `borderRadius: var(--mac-radius-lg)` | `<section className="mac-app-empty" aria-label={title}>` wrapping `<div>` with `background: transparent`, `border: none`, `borderRadius: 0` |
| No outer wrapper | Outer `<section>` adds another DOM level (cosmetic — no visual impact) |
| `role="status"` + `aria-live="polite"` on inner div | `aria-label={title}` on outer section; `role="status"` + `aria-live="polite"` preserved on inner div (via AppEmpty delegating to MacOSEmptyState internally) |
| Icon rendered via `<IconComponent style={iconStyle} />` (iconStyle = `{width: 48, height: 48, color: var(--mac-text-tertiary), opacity: 0.6}`) | Icon wrapped via `normalizeIcon()` → cloned as `<AppEmptyIcon style={iconStyle} />` with same iconStyle merge. **For component-type icons (RefreshCw/Calendar/etc.), iconStyle merge behavior is identical** because `cloneElement` with `{props.style, originalElement.props.style}` for icons that have no original style → result is identical to MacOSEmptyState's `<IconComponent style={iconStyle} />`. |

**Net:** The only visible change is the loss of background/border/radius on the empty state container. All 9 usages render inside admin panel pages where the surrounding layout (admin-* CSS classes) provides visual context — the empty state appearing "frameless" is consistent with the Medical Minimalism direction.

### 3.1 Visual regression safety

- **No existing Playwright visual regression snapshot covers any of the 5 migrated files.** Existing snapshots target `.cashier-*` CSS classes in CashierPanel (which does NOT use MacOSEmptyState).
- **No targeted regression assertion added.** Per user's strict scope rule ("не создавать новый тестовый framework/API"), no new tests were added. Adding snapshot tests for admin panels would require new Playwright spec files — out of scope for this batch.
- **Manual verification recommendation:** Before merge, manually load each affected admin page (`/admin/appointments`, `/admin/patients`, `/admin/doctors`, `/admin/finance`, `/admin/dashboard`) with API failure triggered (e.g., kill backend) to visually confirm the empty state renders without frame, error message visible, retry button works.

---

## 4. Regression gate

All gates run locally on the staged diff.

| Gate | Command | Result | Notes |
|---|---|---|---|
| TypeScript | `npx tsc --noEmit` | ✅ 0 errors | Clean |
| ESLint (5 changed files) | `npx eslint src/components/admin/Admin{Appointments,Patients,Doctors,FinanceOverview,Dashboard}.tsx` | ✅ 0 errors, 21 warnings | All 21 pre-existing (single-quote warnings, same as HEAD baseline; verified by stashing changes and re-running) |
| Vitest | `npx vitest run` | ✅ 165/165 test files, 1218/1218 tests passed (20.48s) | 6 more tests than baseline (1212 → 1218) — delta from `uiBaselineScanner.test.ts` added by main's `da73064` commit, NOT from this PR |
| Vite build | `npx vite build` | ✅ Built successfully in 31.28s | Bundle sizes unchanged |
| Production grep (dead props) | Programmatic check on all 9 `<AppEmpty>` usages | ✅ 0 dead props | All 9 usages use only canonical `{icon, title, description, action}` |
| Production grep (residual MacOSEmptyState) | `grep -c "<MacOSEmptyState"` per file | ✅ AdminAppointments=0, AdminPatients=0, AdminDoctors=0, AdminFinanceOverview=0, AdminDashboard=3 (deferred to Batch 1b) | Matches expected scope |
| e2e (Playwright) | (not run locally) | ⏸ Deferred to CI per `AGENTS_UI.md` contract | Path filter `frontend_e2e` triggers only for `frontend/e2e/**`, `frontend/src/components/{registrar,queue,payment,emr,lab}/**`, `frontend/src/{pages,panels,routing}/**`, `App.jsx`, `PublicApp.jsx`. This PR touches only `frontend/src/components/admin/` — does NOT match. **e2e will be SKIPPED by CI path policy.** |

### 4.1 ESLint warning delta

| File | HEAD warnings | After PR-UI-07a-1a | Delta |
|---|---|---|---|
| AdminAppointments.tsx | 0 | 0 | 0 |
| AdminPatients.tsx | 1 | 1 | 0 |
| AdminDoctors.tsx | 1 | 1 | 0 |
| AdminFinanceOverview.tsx | 11 | 11 | 0 |
| AdminDashboard.tsx | 8 | 8 | 0 |
| **Total** | **21** | **21** | **0** |

All 21 warnings are pre-existing single-quote style issues unrelated to the migration.

---

## 5. Architectural contract check (per `AGENTS_UI.md`)

| Contract rule | Status |
|---|---|
| Don't change canonical primitive APIs | ✅ AppEmpty/AppState.tsx untouched |
| Don't create new primitives without approval | ✅ None created |
| Don't migrate outside approved scope | ✅ Only 5 files / 9 usages touched |
| Don't delete MacOSEmptyState.tsx or its barrel export | ✅ Untouched |
| Preserve existing MacOSEmptyState consumers (B/C/other-A groups) | ✅ All 21 other files untouched |
| Stop after Pre-PR Report, wait for review | ✅ This document is the stop point |

---

## 6. Consumer count delta (per PR-UI-07a inventory)

| Metric | Before PR-UI-07a-1a | After PR-UI-07a-1a | Delta |
|---|---|---|---|
| Files referencing MacOSEmptyState (production) | 30 | 26 (4 files fully migrated, 1 file partially) | -4 fully + 1 partial |
| Production JSX usages | 56 | 47 (9 migrated) | -9 |
| Files referencing AppEmpty (production) | ~14 (existing) | 19 (5 files added) | +5 |

**Note on "30 → 26" arithmetic:** AdminDashboard.tsx still imports MacOSEmptyState (for 3 deferred usages), so it still counts as a MacOSEmptyState consumer. The fully-migrated files are AdminAppointments, AdminPatients, AdminDoctors, AdminFinanceOverview = 4 files. So 30 - 4 = 26 files still reference MacOSEmptyState.

---

## 7. Files changed

```
M frontend/src/components/admin/AdminAppointments.tsx       (+3, -3)
M frontend/src/components/admin/AdminDashboard.tsx           (+2, -1)
M frontend/src/components/admin/AdminDoctors.tsx             (+3, -3)
M frontend/src/components/admin/AdminFinanceOverview.tsx     (+3, -3)
M frontend/src/components/admin/AdminPatients.tsx           (+3, -3)
?? docs/reports/PR_UI_07a_READ_ONLY_INVENTORY.md            (untracked, will be committed as audit trail)
```

**Note:** `docs/reports/PR_UI_07a_READ_ONLY_INVENTORY.md` is the read-only audit document produced in the previous phase. It will be added to the commit as part of the audit trail (consistent with how PR-UI-07 Phase 1 included its Pre-PR Report in the same commit). The user's strict scope rule says "не расширять scope ради полноценного visual redesign" — adding the audit doc as audit-trail is NOT scope expansion, it's documentation of the migration plan.

---

## 8. Pre-PR checklist

- [x] 5 production files modified (only the approved 5)
- [x] 9 usages migrated (verified by grep)
- [x] 0 dead props transferred (programmatic verification)
- [x] All gates green (tsc=0, eslint=0 errors / 21 pre-existing warnings, vitest=1218/1218, build=success)
- [x] Pre-PR Report written (this document)
- [ ] **STOP HERE** — wait for human review
- [ ] Do NOT commit (will be done after review approval)
- [ ] Do NOT push
- [ ] Do NOT open PR
- [ ] Do NOT merge

---

## 9. Suggested PR description (for when review approves)

```markdown
## PR-UI-07a-1a — Admin error-state MacOSEmptyState → AppEmpty (Batch 1a)

First batch of PR-UI-07a migration per `docs/reports/PR_UI_07a_READ_ONLY_INVENTORY.md` (read-only audit report included in this PR).

### What
- Migrate 9 usages across 5 admin files from `<MacOSEmptyState>` to `<AppEmpty>`.
- All 9 usages are error-state fallbacks or empty-state fallbacks after API failure (icon=RefreshCw/Calendar/Users/Stethoscope/CreditCard/AlertCircle, action=retry/create Button).
- Drop-in compatible: all pass `{icon, title, description, action}` props, all of which AppEmpty accepts with identical semantics.
- No prop changes needed; no dead props transferred (programmatic verification).
- AdminDashboard.tsx partial migration: only line 324 (statsError with retry Button) is migrated. The other 3 usages (lines 366, 419, 456 — chart/list empty states without action) are deferred to Batch 1b. AdminDashboard.tsx imports BOTH `AppEmpty` (migrated usage) and `MacOSEmptyState` (deferred usages).

### Files (5 production + 1 audit doc)
- frontend/src/components/admin/AdminAppointments.tsx       2 usages migrated
- frontend/src/components/admin/AdminPatients.tsx          2 usages migrated
- frontend/src/components/admin/AdminDoctors.tsx           2 usages migrated
- frontend/src/components/admin/AdminFinanceOverview.tsx   2 usages migrated
- frontend/src/components/admin/AdminDashboard.tsx         1 usage migrated (3 deferred)
- docs/reports/PR_UI_07a_READ_ONLY_INVENTORY.md            read-only audit (audit trail)

### Net
5 production files changed, +14 / −13 LOC (net +1 LOC).

### Visual behavior delta
- All 9 migrated usages lose `variant="default"` (bg-primary, border, radius-lg).
- AppEmpty forces `variant="minimal"` (transparent bg, no border, no radius).
- Wraps in `<section className="mac-app-empty" aria-label={title}>` (additional outer DOM level, cosmetic).
- Icon visual unchanged for component-type icons (RefreshCw/Calendar/etc.) — AppEmpty's `normalizeIcon()` produces identical rendering for non-ReactElement icons.

### Regression gate (all green)
- tsc --noEmit: 0 errors
- eslint: 0 errors (21 pre-existing warnings, 0 delta from HEAD)
- vitest: 165/165 files, 1218/1218 tests passed (20.48s)
- vite build: success (31.28s)
- Programmatic prop check: 9/9 usages use only canonical `{icon, title, description, action}` — 0 dead props
- e2e: unverified — skipped by CI path policy (admin files not in frontend_e2e filter)

### Out of scope (deferred to subsequent batches)
- 3 remaining AdminDashboard.tsx usages (lines 366, 419, 456) → PR-UI-07a-1b (Batch 1b)
- All other MacOSEmptyState consumers → subsequent PR-UI-07a-* batches
- StateWrapper.tsx refactor (high-risk, has latent bugs) → PR-UI-07a-3 (Batch 3)
- DermatologistPanelUnified.tsx (icon="calendar" string → Calendar component) → PR-UI-07a-4 (Batch 4)
- MacOSEmptyState.tsx deletion + barrel export removal → PR-UI-07a-8 (Batch 8, after all consumers migrated)

### Pre-PR Reports
- Full compatibility matrix + per-consumer analysis: `docs/reports/PR_UI_07a_READ_ONLY_INVENTORY.md` (committed in this PR)
- This PR's pre-PR report: `docs/reports/PR_UI_07a_1a_PRE_PR_REPORT.md`

### Reviewer guidance
This is a low-risk mechanical migration of dead-code-cleanup type. Safe to merge after CI passes. **Do not merge automatically** — wait for human review.
```

---

**End of Pre-PR Report. Awaiting review.**
