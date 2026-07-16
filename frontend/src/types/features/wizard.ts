// src/types/features/wizard.ts
// Phase 0.5 — Wizard domain UI types (placeholder).
// Will be filled in during Phase 5.15 (wizard components migration).
// ⚠️ Wizard files are >500 lines and require decomposition BEFORE TS migration
// (AppointmentWizardV2.jsx is 2970 lines per the plan).
//
// SSOT:
//   - frontend/src/components/wizard/ (will be decomposed first)
//   - backend OpenAPI schemas: AppointmentCreate, ServiceOut, etc.

// TODO Phase 5.15: WizardStep, WizardState, WizardFormValues
export type WizardStep = 'services' | 'patient' | 'schedule' | 'review' | 'confirmation' | string;
export type WizardState = Record<string, unknown>;
