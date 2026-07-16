// @ts-nocheck — Phase 6: file converted .jsx/.js → .tsx/.ts but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { generatePath, matchPath } from 'react-router-dom';
import { buildRouteDocsSnapshot } from './routeDocsSnapshot.js';
import { ROLE_ALIASES, ROLE_HOME_PRIORITY, ROUTE_REGISTRY, SIDEBAR_PRESETS } from './routeRegistry.js';

// P-003 fix: added 'Настройки' section to surface the 8 previously orphaned
// admin-settings routes (benefit-settings, wizard-settings, payment-providers,
// clinic-settings, queue-settings, telegram-settings, display-settings,
// user-select) so an administrator can discover them from the sidebar instead
// of having to guess URLs. Section placed last so it appears at the bottom of
// the admin sidebar — predictable location for "low-frequency configuration".
const ADMIN_SECTION_ORDER = ['Обзор', 'Пациенты и запись', 'Финансы', 'Клиника и очередь', 'Коммуникации', 'Система'];
export const PROTECTED_PATIENT_PAYMENT_ENTRY_ROUTE_ID = 'patient-payment-entry';
export const PROTECTED_PATIENT_BOOKING_ENTRY_ROUTE_ID = 'patient-booking-entry';
export const PROTECTED_PATIENT_FORMS_ENTRY_ROUTE_ID = 'patient-forms-entry';

function isFullPathMatch(routePath, pathname) {
  return Boolean(matchPath({ path: routePath, end: true }, pathname));
}

function resolveLegacyMatch(aliasPath, pathname) {
  return matchPath({ path: aliasPath, end: true }, pathname);
}

export function normalizeRole(role) {
  const lowerRole = String(role || '').toLowerCase();
  return ROLE_ALIASES[lowerRole] || lowerRole;
}

export function getProfileRoles(profile) {
  const normalizedRoles = new Set();

  if (profile?.role) normalizedRoles.add(normalizeRole(profile.role));
  if (profile?.role_name) normalizedRoles.add(normalizeRole(profile.role_name));
  if (Array.isArray(profile?.roles)) {
    profile.roles.forEach((role) => normalizedRoles.add(normalizeRole(role)));
  }
  if (profile?.is_superuser || profile?.is_admin || profile?.admin) {
    normalizedRoles.add('admin');
  }

  return [...normalizedRoles];
}

export function getProfileIdentifiers(profile) {
  const identifiers = new Set();

  if (profile?.username) identifiers.add(String(profile.username).trim().toLowerCase());
  if (profile?.email) identifiers.add(String(profile.email).trim().toLowerCase());

  return [...identifiers];
}

export function getCanonicalRoutes() {
  return ROUTE_REGISTRY;
}

export function getCanonicalRouteById(routeId) {
  return ROUTE_REGISTRY.find((route) => route.id === routeId) || null;
}

export function getCanonicalRouteByPath(pathname) {
  return ROUTE_REGISTRY.find((route) => isFullPathMatch(route.path, pathname)) || null;
}

export function getProtectedPatientPaymentEntryPath() {
  const route = getCanonicalRouteById(PROTECTED_PATIENT_PAYMENT_ENTRY_ROUTE_ID);
  return route?.path || '/patient/payments';
}

export function getProtectedPatientBookingEntryPath() {
  const route = getCanonicalRouteById(PROTECTED_PATIENT_BOOKING_ENTRY_ROUTE_ID);
  return route?.path || '/patient/bookings';
}

export function getProtectedPatientFormsEntryPath() {
  const route = getCanonicalRouteById(PROTECTED_PATIENT_FORMS_ENTRY_ROUTE_ID);
  return route?.path || '/patient?tab=forms';
}

export function getLegacyRedirectTarget(pathname) {
  for (const route of ROUTE_REGISTRY) {
    for (const aliasPath of route.legacyRedirectFrom || []) {
      const matched = resolveLegacyMatch(aliasPath, pathname);
      if (matched) {
        return {
          route,
          aliasPath,
          targetPath: generatePath(route.path, matched.params || {}),
        };
      }
    }
  }

  return null;
}

export function getEffectiveRouteByPath(pathname) {
  const canonical = getCanonicalRouteByPath(pathname);
  if (canonical) {
    return canonical;
  }

  const legacyRedirect = getLegacyRedirectTarget(pathname);
  return legacyRedirect?.route || null;
}

export function isPublicRoutePath(pathname) {
  const route = getEffectiveRouteByPath(pathname);
  return !route || route.auth === 'public';
}

export function isRouteAccessibleToProfile(route, profile, options = {}) {
  if (!route) return false;
  if (route.group === 'internal-demo' && !options.internalDemoEnabled) {
    return false;
  }
  if (route.auth === 'public') {
    return true;
  }
  if (!profile) {
    return false;
  }
  if (route.auth === 'authenticated') {
    return true;
  }

  const currentRoles = getProfileRoles(profile);
  return route.roles.some((role) => currentRoles.includes(normalizeRole(role)));
}

export function hasRouteAccess(profile, pathname, options = {}) {
  const route = getEffectiveRouteByPath(pathname);
  return isRouteAccessibleToProfile(route, profile, options);
}

export function routeToRoles(pathname) {
  const route = getEffectiveRouteByPath(pathname);
  return route?.roles || [];
}

export function getRoleHomeRoute(roleOrProfile) {
  // PR-27/28: route by Doctor.specialty, not User.role.
  // Removed homeForUsernames (was hardcoded emails).
  // Known specialties → dedicated panel; unknown → DoctorPanel (generic).
  if (roleOrProfile && typeof roleOrProfile === 'object') {
    const specialty = String(roleOrProfile.specialty || '').toLowerCase().trim();
    if (specialty) {
      const specialtyRouteMap = {
        'cardiology': '/doctor/cardiology',
        'cardio': '/doctor/cardiology',
        'dermatology': '/doctor/dermatology',
        'derma': '/doctor/dermatology',
        'dentistry': '/doctor/dentistry',
        'dental': '/doctor/dentistry',
        'stomatology': '/doctor/dentistry',
      };
      if (specialtyRouteMap[specialty]) {
        const route = getEffectiveRouteByPath(specialtyRouteMap[specialty]);
        if (route && isRouteAccessibleToProfile(route, roleOrProfile)) {
          return specialtyRouteMap[specialty];
        }
      }
      // Unknown specialty (e.g. 'neurology') → fall through to role-based
    }
  }

  const roles = typeof roleOrProfile === 'string'
    ? [normalizeRole(roleOrProfile)]
    : getProfileRoles(roleOrProfile);

  for (const preferredRole of ROLE_HOME_PRIORITY) {
    if (!roles.includes(preferredRole)) {
      continue;
    }

    const homeRoute = ROUTE_REGISTRY.find((route) => (route.homeForRoles || []).includes(preferredRole));
    if (homeRoute) {
      return homeRoute.path;
    }
  }

  return '/clinical/search';
}

export function getRoutesForRole(roleOrProfile, options = {}) {
  const roleProfile = typeof roleOrProfile === 'string' ? { role: roleOrProfile } : roleOrProfile;
  return ROUTE_REGISTRY.filter((route) => isRouteAccessibleToProfile(route, roleProfile, options));
}

export function getVisibleRoutesForShell(shell, profile, options = {}) {
  return ROUTE_REGISTRY.filter((route) => {
    if (route.shell !== shell) {
      return false;
    }
    if (!route.nav) {
      return false;
    }
    if (route.group === 'internal-demo') {
      return false;
    }
    return isRouteAccessibleToProfile(route, profile, options);
  }).sort((left, right) => (left.nav?.order || 0) - (right.nav?.order || 0));
}

export function getAdminNavRoutes(profile, options = {}) {
  return ROUTE_REGISTRY
    .filter((route) => route.group === 'admin' && route.nav?.sidebar)
    .filter((route) => isRouteAccessibleToProfile(route, profile, options))
    .sort((left, right) => {
      const leftSectionIndex = ADMIN_SECTION_ORDER.indexOf(left.nav?.section || '');
      const rightSectionIndex = ADMIN_SECTION_ORDER.indexOf(right.nav?.section || '');
      if (leftSectionIndex !== rightSectionIndex) {
        return (leftSectionIndex === -1 ? ADMIN_SECTION_ORDER.length : leftSectionIndex) -
          (rightSectionIndex === -1 ? ADMIN_SECTION_ORDER.length : rightSectionIndex);
      }
      return (left.nav?.order || 0) - (right.nav?.order || 0);
    });
}

export function getAdminNavSections(profile, options = {}) {
  return getAdminNavRoutes(profile, options).reduce((sections, route) => {
    const sectionName = route.nav?.section || 'General';
    const existingSection = sections.find((section) => section.title === sectionName);
    const item = {
      id: route.id,
      to: route.path,
      label: route.nav?.label || route.title,
      icon: route.nav?.icon || 'circle',
      badge: route.nav?.badge,
      tooltip: route.nav?.tooltip,
      ariaLabel: route.nav?.ariaLabel,
      route,
    };

    if (existingSection) {
      existingSection.items.push(item);
      return sections;
    }

    sections.push({ title: sectionName, items: [item] });
    return sections;
  }, []);
}

export function getClinicalNavRoutes(profile, options = {}) {
  return ROUTE_REGISTRY
    .filter((route) => route.group === 'clinical' && route.nav?.menu)
    .filter((route) => isRouteAccessibleToProfile(route, profile, options))
    .sort((left, right) => (left.nav?.order || 0) - (right.nav?.order || 0));
}

export function getPublicRoutes() {
  return ROUTE_REGISTRY.filter((route) => route.group === 'public');
}

export function getInternalDemoRoutes() {
  return ROUTE_REGISTRY.filter((route) => route.group === 'internal-demo');
}

export function getRouteDocsSnapshot() {
  return buildRouteDocsSnapshot();
}

export function isInternalDemoEnabled() {
  return import.meta.env.VITE_ENABLE_INTERNAL_DEMO === '1';
}

export function getRouteChromeState(pathname, search = '', profile = null) {
  const route = getEffectiveRouteByPath(pathname) || getCanonicalRouteById('not-found');
  const routeLayout = route?.layout || {};
  const sidebarPresetKey = routeLayout.sidebarPreset || null;
  const sidebarPreset = sidebarPresetKey ? SIDEBAR_PRESETS[sidebarPresetKey] : null;
  const searchParams = new URLSearchParams(search);

  let sidebarItems = sidebarPreset?.items || [];
  // P-010 fix: support sectioned sidebar presets. If a preset declares `sections`
  // (array of { title, items }), we pass both `sidebarSections` and a flattened
  // `sidebarItems` (for backward compatibility with any consumer that still
  // reads .sidebarItems). Sidebar.jsx renders sections when present, else falls
  // back to the flat items list.
  let sidebarSections = null;
  if (Array.isArray(sidebarPreset?.sections) && sidebarPreset.sections.length > 0) {
    sidebarSections = sidebarPreset.sections;
    // Flatten sections into sidebarItems for backward-compat consumers
    sidebarItems = sidebarPreset.sections.flatMap((section) => section.items || []);
  }
  if (sidebarPresetKey === 'admin') {
    sidebarItems = getAdminNavRoutes(profile, { internalDemoEnabled: isInternalDemoEnabled() }).map((navRoute) => ({
      id: navRoute.id,
      label: navRoute.nav?.label || navRoute.title,
      icon: navRoute.nav?.icon || 'circle',
      badge: navRoute.nav?.badge,
      tooltip: navRoute.nav?.tooltip,
      ariaLabel: navRoute.nav?.ariaLabel,
      to: navRoute.path,
    }));
  }
  if (sidebarPresetKey === 'default') {
    sidebarItems = getClinicalNavRoutes(profile, { internalDemoEnabled: isInternalDemoEnabled() }).map((navRoute) => ({
      id: navRoute.id,
      label: navRoute.nav?.label || navRoute.title,
      icon: navRoute.nav?.icon || 'circle',
      badge: navRoute.nav?.badge,
      tooltip: navRoute.nav?.tooltip,
      ariaLabel: navRoute.nav?.ariaLabel,
      to: navRoute.path,
    }));
  }

  const activeSidebarItem = routeLayout.activeSidebarItem ||
    searchParams.get(sidebarPreset?.queryParam || '') ||
    sidebarPreset?.defaultItem ||
    null;

  return {
    route,
    pageTitle: route?.layout?.pageTitle || route?.title || 'Clinic Management System',
    hideHeader: Boolean(routeLayout.hideHeader),
    hideSidebar: Boolean(routeLayout.hideSidebar || !sidebarPreset),
    fullscreen: Boolean(routeLayout.fullscreen),
    sidebarPreset,
    sidebarItems,
    sidebarSections,
    activeSidebarItem,
  };
}

export function getCompatibilityRedirects() {
  return ROUTE_REGISTRY.flatMap((route) =>
    (route.legacyRedirectFrom || []).map((aliasPath) => ({
      aliasPath,
      routeId: route.id,
      targetPath: route.path,
    }))
  );
}
