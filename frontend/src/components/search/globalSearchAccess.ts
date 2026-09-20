// NURSE-V2 N2-2 (review P2 round 3 — PR #3333): frontend mirror of the
// backend GLOBAL_SEARCH_ROLES allowlist
// (backend/app/api/v1/endpoints/global_search.py). GET /api/v1/global-search
// is require_roles-gated to exactly those roles — every other role (Nurse,
// Patient, ...) answers 403. The GlobalSearchBar self-gates on this mirror
// so app-shell surfaces that are open to non-search roles (the NURSE-V2
// nurse home /clinical/profile mounts the header, and with it this bar)
// never ship a control whose every request is guaranteed to fail and be
// swallowed into an empty "nothing found" result.
//
// Keep the spelling set in sync with the backend tuple. Comparison is
// case-insensitive so the mixed-case legacy variants the backend carries
// ("Lab"/"Laboratory", "cardio"/"cardiology"/"Cardiologist", ...) all match
// regardless of which spelling a stored profile uses.

const GLOBAL_SEARCH_ROLES: ReadonlySet<string> = new Set([
  'admin',
  'registrar',
  'doctor',
  'cashier',
  'lab',
  'laboratory',
  'cardio',
  'cardiology',
  'cardiologist',
  'derma',
  'dermatologist',
  'dentist',
]);

export interface GlobalSearchAccessProfile {
  role?: string | null;
  role_name?: string | null;
  roles?: unknown;
  [key: string]: unknown;
}

function collectProfileRoles(
  profile: GlobalSearchAccessProfile | null | undefined,
): string[] {
  if (!profile) return [];
  const roles: string[] = [];
  const single = profile.role ?? profile.role_name;
  if (typeof single === 'string' && single) {
    roles.push(single.toLowerCase());
  }
  if (Array.isArray(profile.roles)) {
    for (const entry of profile.roles) {
      if (typeof entry === 'string' && entry) {
        roles.push(entry.toLowerCase());
      }
    }
  }
  return roles;
}

/**
 * True when ANY of the profile's roles is allowed to call /global-search.
 * Fail closed: a missing profile or a profile without a recognizable role
 * grants nothing.
 */
export function canUseGlobalSearch(
  profile: GlobalSearchAccessProfile | null | undefined,
): boolean {
  return collectProfileRoles(profile).some((role) => GLOBAL_SEARCH_ROLES.has(role));
}
