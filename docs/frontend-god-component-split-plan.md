# Frontend God Component Split Plan

**Date:** 2026-07-12
**Author:** Super Z (z.ai)
**Related audit findings:** High-15 (11 god components >500 LOC), P0-19 (~9400 hardcoded strings)

## Problem

The frontend has 11 components exceeding 500 LOC. The top-5 are:

| Component | LOC | Responsibilities |
|-----------|-----|------------------|
| `AppointmentWizardV2.jsx` | 3015 | Multi-step wizard: patient lookup, service selection, cart, payment, confirmation, editing |
| `TelegramMiniAppPatientShell.jsx` | 2601 | Telegram Mini App: routing, appointments, profile, notifications, onboarding |
| `EnhancedAppointmentsTable.jsx` | 2596 | Appointment table: filtering, sorting, pagination, row expansion, inline editing, bulk actions |
| `TelegramManager.jsx` | 2372 | Admin Telegram bot management: templates, onboarding review, command registration, analytics |
| `DentistPanelUnified.jsx` | 2349 | Dentist dashboard: appointments, patients, protocols, services, photo archive |

These components are hard to maintain, test, and review. A single change can have unintended side effects across unrelated features.

## Split Strategy

### 1. AppointmentWizardV2.jsx (3015 LOC → 5 sub-components)

**Extract:**
- `PatientLookupStep.jsx` (~400 LOC) — patient search + create
- `ServiceSelectionStep.jsx` (~600 LOC) — service catalog + cart
- `PaymentStep.jsx` (~500 LOC) — payment method + processing
- `ConfirmationStep.jsx` (~300 LOC) — summary + confirm
- `EditModeBanner.jsx` (~200 LOC) — edit-mode banner + QueueJoin badges

**Shared state:** lift to `useWizardState()` hook (already exists as `useWizardState`).

### 2. TelegramMiniAppPatientShell.jsx (2601 LOC → 4 sub-components)

**Extract:**
- `MiniAppAppointments.jsx` (~600 LOC) — appointment list + booking
- `MiniAppProfile.jsx` (~400 LOC) — profile view + edit
- `MiniAppNotifications.jsx` (~300 LOC) — notification center
- `MiniAppOnboarding.jsx` (~500 LOC) — first-time onboarding flow

**Shared state:** `useMiniAppUser()` hook (already exists).

### 3. EnhancedAppointmentsTable.jsx (2596 LOC → 3 sub-components)

**Extract:**
- `AppointmentFilters.jsx` (~400 LOC) — filter bar + saved filters
- `AppointmentRow.jsx` (~300 LOC) — single row + expanded view
- `AppointmentBulkActions.jsx` (~200 LOC) — bulk select + actions

**Shared state:** `useAppointmentFilters()` hook.

### 4. TelegramManager.jsx (2372 LOC → 4 sub-components)

**Extract:**
- `TelegramTemplates.jsx` (~400 LOC) — template CRUD
- `TelegramOnboardingReview.jsx` (~600 LOC) — onboarding request review + duplicate candidates
- `TelegramCommandRegistration.jsx` (~300 LOC) — command registration UI
- `TelegramAnalytics.jsx` (~400 LOC) — analytics dashboard

**Shared state:** `useTelegramBotStatus()` hook.

### 5. DentistPanelUnified.jsx (2349 LOC → 5 sub-components)

**Extract:**
- `DentistAppointments.jsx` (~500 LOC) — appointment list + queue
- `DentistPatients.jsx` (~400 LOC) — patient list + search
- `DentistProtocols.jsx` (~400 LOC) — visit protocols
- `DentistServices.jsx` (~300 LOC) — service catalog
- `DentistPhotoArchive.jsx` (~300 LOC) — photo archive

**Shared state:** `useDentistPanelData()` hook (already exists as `loadData`).

## Execution Plan

Each split is a separate PR:
- PR-45: AppointmentWizardV2 split
- PR-46: TelegramMiniAppPatientShell split
- PR-47: EnhancedAppointmentsTable split
- PR-48: TelegramManager split
- PR-49: DentistPanelUnified split

Each PR:
1. Extracts sub-components without changing behavior
2. Adds characterization tests before refactoring
3. Runs full regression after extraction
4. No new features — pure refactor

## P0-19: Hardcoded String Extraction

The 9400 hardcoded Russian strings will be extracted incrementally as each god component is split. The pattern (demonstrated in PR-44 with PhoneVerification.jsx):

1. Add keys to `src/hooks/useTranslation.jsx` (ru/uz/en)
2. Import `useTranslation` in the component
3. Replace hardcoded strings with `t('key')`
4. Test that all 3 locales render correctly

**Estimated effort:** 2-3 strings per component per PR. Full extraction is a multi-quarter effort.

## Current Status

- **PR-44 (this PR):** PhoneVerification.jsx title extracted to i18n (8 new keys × 3 locales = 24 translations)
- **Remaining:** ~9392 hardcoded strings across 250 files
- **God components:** 0/5 split (plan documented, execution pending)
