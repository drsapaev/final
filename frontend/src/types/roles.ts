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
  | 'Manager'
  | 'cardio'
  | 'derma'
  | 'dentist'
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
  'Registrar', 'Lab', 'Cashier', 'Nurse',
] as const;

// ============================================================================
// Role hierarchy levels — mirror backend get_role_hierarchy().
// Source: backend/app/core/roles.py lines 89-106
// Higher number = more privileges.
// ============================================================================

export const ROLE_LEVEL: Readonly<Record<BackendRole, number>> = {
  Patient: 1,
  Nurse: 2,
  // E-4: Receptionist: 3 retired with the spelling (§4.1.27).
  Cashier: 4,
  Lab: 5,
  Registrar: 6,
  Doctor: 7,
  cardio: 7,
  derma: 7,
  dentist: 7,
  Manager: 8,
  Admin: 9,
  SuperAdmin: 10,
} as const;

// ============================================================================
// Role aliases — mirror routeRegistry ROLE_ALIASES.
// Frontend-only mapping; not in backend.
// REC-3 (Receptionist deprecation): the receptionist -> registrar alias was
// removed — Registrar is the canonical front-desk role and the legacy
// spelling no longer reaches registrar routes (route parity test pins the
// deny). The nurse -> doctor alias is a separate policy decision and is
// intentionally untouched.
// ============================================================================

export const ROLE_ALIASES: Readonly<Record<string, FrontendRoleKey>> = {
  nurse: 'doctor',
} as const;

// ============================================================================
// Type guards
// ============================================================================

export function isBackendRole(value: unknown): value is BackendRole {
  return (
    typeof value === 'string' &&
    (
      value === 'Admin' || value === 'Registrar' || value === 'Doctor' ||
      value === 'Lab' || value === 'Cashier' || value === 'Manager' ||
      value === 'cardio' || value === 'derma' || value === 'dentist' ||
      value === 'Nurse' || value === 'Patient' ||
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
