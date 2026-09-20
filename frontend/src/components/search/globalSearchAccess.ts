// NURSE-V2 N2-2 (review P2 round 3 — PR 3333 + codex round): frontend mirror
// of the backend GLOBAL_SEARCH_ROLES allowlist
// (backend/app/api/v1/endpoints/global_search.py). GET /api/v1/global-search
// is gated by require_roles(*GLOBAL_SEARCH_ROLES); the GlobalSearchBar
// self-gates on this mirror so app-shell surfaces that are open to
// non-search roles (the NURSE-V2 nurse home /clinical/profile mounts the
// header, and with it this bar) never ship a control whose every request
// is guaranteed to fail and be swallowed into an empty "nothing found"
// result.
//
// The grant computation mirrors app/core/security.py::require_roles
// EXACTLY (codex review: the first draft consulted profile.roles /
// role_name, which the backend never checks — over-inclusive for
// {role:'Nurse', roles:['Registrar']}, under-inclusive for a superuser):
//   1. is_superuser -> admitted unconditionally (the backend bypass);
//   2. otherwise the SINGLE primary role column (GET /auth/me exposes
//      exactly `role` + `is_superuser` — no roles array, no role_name)
//      is compared case-insensitively against the allowlist, exactly like
//      the backend lowercases both sides;
//   3. anything else fails closed.
// The backend boundary stays the source of truth for PHI; keep the
// spelling set in sync with the backend tuple.

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
  is_superuser?: boolean | null;
  [key: string]: unknown;
}

/**
 * Mirrors require_roles(*GLOBAL_SEARCH_ROLES): a superuser is admitted
 * unconditionally; every other profile is judged by its single primary
 * role, case-insensitively. Fail closed: no profile, no search bar.
 */
export function canUseGlobalSearch(
  profile: GlobalSearchAccessProfile | null | undefined,
): boolean {
  if (!profile) return false;
  if (profile.is_superuser === true) return true;
  const role = typeof profile.role === 'string' ? profile.role.toLowerCase() : '';
  return GLOBAL_SEARCH_ROLES.has(role);
}
