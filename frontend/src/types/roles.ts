// src/types/roles.ts
// Phase 0.5 — Roles SSOT.
// Plan: JS-to-TS-Migration-Plan v3, section 0.5.3
//
// SSOT: backend/app/core/roles.py — Roles(str, Enum)
// ⚠️ ВНИМАНИЕ: специалистные роли — lowercase, остальные — TitleCase/PascalCase.
// Это не опечатка — это фактический casing из backend enum.

export type BackendRole =
  | 'Admin'
  | 'Registrar'
  | 'Doctor'
  | 'Lab'
  | 'Cashier'
  // M-2 (Manager vocabulary closure, 2026-09-05): 'Manager' removed —
  // mirrors backend core/roles.py. The single stored row (smoke_manager,
  // id=20) was deactivated by ops (is_active=false); the tombstone keeps
  // role='Manager' as a raw string, which no longer matches this union —
  // acceptable because the account cannot log in and the frontend has
  // zero 'manager' role-key surfaces (registry/sidebar/homeForRoles).
  | 'cardio'
  | 'derma'
  | 'dentist'
  // NURSE-V2 (owner design-GO 2026-09-19): 'Nurse' re-opened as a NEW
  // product capability (human non-doctor clinical serving) — mirrors the
  // backend core/roles.py enum re-open. N-3 history stands: the old role
  // never shipped as a product surface (0 rows, census 2026-09-05). The
  // new Nurse starts privilege-zero: no role-scoped routes/sidebar here
  // until the N2-3 serving API and the N2-5 tablet surface land. The one
  // sanctioned exception (review P2, PR #3333): the Nurse login landing
  // is the auth:'authenticated' /clinical/profile page — a safe home so a
  // successful login does not bounce to /forbidden; it grants nothing.
  | 'Nurse'
  // E-4 (Receptionist alias removal): 'Receptionist' removed — mirrors the
  // backend core/roles.py enum decommission (§4.1.27). Canonical Registrar
  // is the front-desk role; the legacy spelling had 0 stored rows.
  | 'Patient'
  | 'SuperAdmin';

/**
 * Frontend-internal: lowercase keys для homeForRoles, sidebar presets.
 * Derived from BackendRole — do not edit manually.
 */
export type FrontendRoleKey = Lowercase<BackendRole>;

// ============================================================================
// Role sets — mirror backend/app/core/roles.py exactly.
// Source: backend/app/core/roles.py lines 33-66
// ============================================================================

export const CRITICAL_ROLES: readonly BackendRole[] = [
  'Admin', 'Registrar', 'Lab', 'Doctor', 'Cashier', 'cardio', 'derma', 'dentist',
] as const;

export const ADMIN_ROLES: readonly BackendRole[] = [
  // M-1 (Manager deprecation): 'Manager' removed — mirrors backend
  // core/roles.py ADMIN_ROLES (zero callers on either side, verified by
  // exhaustive search; removal is behavior-neutral).
  'Admin', 'SuperAdmin',
] as const;

export const DOCTOR_ROLES: readonly BackendRole[] = [
  'Doctor', 'cardio', 'derma', 'dentist',
] as const;

export const STAFF_ROLES: readonly BackendRole[] = [
  // E-4: 'Receptionist' removed — canonical Registrar is the front-desk
  // staff role (mirror of backend core/roles.py STAFF_ROLES, §4.1.27).
  'Registrar', 'Lab', 'Cashier',
] as const;

// ============================================================================
// Role hierarchy levels — mirror backend get_role_hierarchy().
// Source: backend/app/core/roles.py lines 89-106
// Higher number = more privileges.
// ============================================================================

export const ROLE_LEVEL: Readonly<Record<BackendRole, number>> = {
  Patient: 1,
  // NURSE-V2 (owner design-GO 2026-09-19): Nurse re-opened at level 2 —
  // mirrors backend get_role_hierarchy(); descriptive only.
  Nurse: 2,
  // E-4: Receptionist: 3 retired with the spelling (§4.1.27).
  Cashier: 4,
  Lab: 5,
  Registrar: 6,
  Doctor: 7,
  cardio: 7,
  derma: 7,
  dentist: 7,
  // M-2: Manager: 8 retired with the spelling (mirrors backend
  // get_role_hierarchy, which now scores a raw 'Manager' string 0).
  Admin: 9,
  SuperAdmin: 10,
} as const;

// ============================================================================
// Role aliases — mirror routeRegistry ROLE_ALIASES.
// Frontend-only mapping; not in backend.
// REC-3 (Receptionist deprecation): the receptionist -> registrar alias was
// removed — Registrar is the canonical front-desk role and the legacy
// spelling no longer reaches registrar routes (route parity test pins the
// deny). N-3 (Nurse retirement): the nurse -> doctor alias removed
// (0 stored rows, production census 2026-09-05).
// NURSE-V2 (owner design-GO 2026-09-19): the alias STAYS removed — the
// new Nurse is NOT a doctor alias and gets no doctor routes; serving
// surfaces arrive with the N2-3 API and the N2-5 tablet page.
// ============================================================================

export const ROLE_ALIASES: Readonly<Record<string, FrontendRoleKey>> = {} as const;

// ============================================================================
// Type guards
// ============================================================================

export function isBackendRole(value: unknown): value is BackendRole {
  return (
    typeof value === 'string' &&
    (
      value === 'Admin' || value === 'Registrar' || value === 'Doctor' ||
      value === 'Lab' || value === 'Cashier' ||
      // M-2: 'Manager' removed from the guard — the deprecated spelling
      // fails the type guard (mirrors the backend enum closure).
      value === 'cardio' || value === 'derma' || value === 'dentist' ||
      // NURSE-V2: 'Nurse' re-opened — mirrors the backend enum.
      value === 'Nurse' ||
      value === 'Patient' ||
      value === 'SuperAdmin'
    )
  );
}

export function isAdminRole(role: BackendRole): boolean {
  return (ADMIN_ROLES as readonly string[]).includes(role);
}

export function isDoctorRole(role: BackendRole): boolean {
  return (DOCTOR_ROLES as readonly string[]).includes(role);
}

export function isStaffRole(role: BackendRole): boolean {
  return (STAFF_ROLES as readonly string[]).includes(role);
}

export function isCriticalRole(role: BackendRole): boolean {
  return (CRITICAL_ROLES as readonly string[]).includes(role);
}

export function getRoleHierarchy(role: BackendRole): number {
  return ROLE_LEVEL[role] ?? 0;
}

export function hasRolePermission(userRole: BackendRole, requiredRole: BackendRole): boolean {
  return getRoleHierarchy(userRole) >= getRoleHierarchy(requiredRole);
}
