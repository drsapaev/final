import { generatePath, matchPath, type PathMatch } from 'react-router-dom';
import { buildRouteDocsSnapshot, type RouteDocsSnapshot } from './routeDocsSnapshot.js';
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

// Route registry is defined in routeRegistry.ts which is currently implicit-any.
// We model the canonical surface we read here and access fields defensively.
interface RouteNavMeta {
  label?: string;
  icon?: string;
  badge?: string;
  tooltip?: string;
  ariaLabel?: string;
  order?: number;
  sidebar?: boolean;
  menu?: boolean;
  section?: string;
  [key: string]: unknown;
}

interface RouteLayout {
  pageTitle?: string;
  hideHeader?: boolean;
  hideSidebar?: boolean;
  fullscreen?: boolean;
  sidebarPreset?: string;
  activeSidebarItem?: string;
  [key: string]: unknown;
}

interface RouteRegistryEntry {
  id: string;
  path: string;
  group: string;
  surface?: string;
  lifecycle: string;
  shell?: string;
  auth: string;
  roles: string[];
  entry: string;
  nav?: RouteNavMeta | boolean;
  title: string;
  owner?: string;
  component?: string;
  homeForRoles?: string[];
  legacyRedirectFrom?: string[];
  layout?: RouteLayout;
  [key: string]: unknown;
}

interface RouteProfile {
  role?: string;
  role_name?: string;
  roles?: string[];
  is_superuser?: boolean;
  is_admin?: boolean;
  admin?: boolean;
  username?: string;
  email?: string;
  specialty?: string;
  [key: string]: unknown;
}

interface SidebarItem {
  id: string;
  to: string;
  label: string;
  icon: string;
  badge?: string;
  tooltip?: string;
  ariaLabel?: string;
  route?: RouteRegistryEntry;
}

interface SidebarSection {
  title: string;
  items: SidebarItem[];
}

interface SidebarPreset {
  items?: SidebarItem[];
  sections?: SidebarSection[];
  queryParam?: string;
  defaultItem?: string;
  [key: string]: unknown;
}

interface AccessOptions {
  internalDemoEnabled?: boolean;
  [key: string]: unknown;
}

interface LegacyRedirectTarget {
  route: RouteRegistryEntry;
  aliasPath: string;
  targetPath: string;
}

interface RouteChromeState {
  route: RouteRegistryEntry | null;
  pageTitle: string;
  hideHeader: boolean;
  hideSidebar: boolean;
  fullscreen: boolean;
  sidebarPreset: SidebarPreset | null;
  sidebarItems: SidebarItem[];
  sidebarSections: SidebarSection[] | null;
  activeSidebarItem: string | null;
}

interface CompatibilityRedirect {
  aliasPath: string;
  routeId: string;
  targetPath: string;
}

const typedRegistry = ROUTE_REGISTRY as RouteRegistryEntry[];

function isFullPathMatch(routePath: string, pathname: string): boolean {
  return Boolean(matchPath({ path: routePath, end: true }, pathname));
}

function resolveLegacyMatch(aliasPath: string, pathname: string): PathMatch | null {
  return matchPath({ path: aliasPath, end: true }, pathname);
}

export function normalizeRole(role: unknown): string {
  const lowerRole = String(role || '').toLowerCase();
  const aliases = ROLE_ALIASES as Record<string, string>;
  return aliases[lowerRole] || lowerRole;
}

export function getProfileRoles(profile: RouteProfile | null | undefined): string[] {
  const normalizedRoles = new Set<string>();

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

export function getProfileIdentifiers(profile: RouteProfile | null | undefined): string[] {
  const identifiers = new Set<string>();

  if (profile?.username) identifiers.add(String(profile.username).trim().toLowerCase());
  if (profile?.email) identifiers.add(String(profile.email).trim().toLowerCase());

  return [...identifiers];
}

export function getCanonicalRoutes(): RouteRegistryEntry[] {
  return typedRegistry;
}

export function getCanonicalRouteById(routeId: string): RouteRegistryEntry | null {
  return typedRegistry.find((route) => route.id === routeId) || null;
}

export function getCanonicalRouteByPath(pathname: string): RouteRegistryEntry | null {
  return typedRegistry.find((route) => isFullPathMatch(route.path, pathname)) || null;
}

export function getProtectedPatientPaymentEntryPath(): string {
  const route = getCanonicalRouteById(PROTECTED_PATIENT_PAYMENT_ENTRY_ROUTE_ID);
  return route?.path || '/patient/payments';
}

export function getProtectedPatientBookingEntryPath(): string {
  const route = getCanonicalRouteById(PROTECTED_PATIENT_BOOKING_ENTRY_ROUTE_ID);
  return route?.path || '/patient/bookings';
}

export function getProtectedPatientFormsEntryPath(): string {
  const route = getCanonicalRouteById(PROTECTED_PATIENT_FORMS_ENTRY_ROUTE_ID);
  return route?.path || '/patient?tab=forms';
}

export function getLegacyRedirectTarget(pathname: string): LegacyRedirectTarget | null {
  for (const route of typedRegistry) {
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

export function getEffectiveRouteByPath(pathname: string): RouteRegistryEntry | null {
  const canonical = getCanonicalRouteByPath(pathname);
  if (canonical) {
    return canonical;
  }

  const legacyRedirect = getLegacyRedirectTarget(pathname);
  return legacyRedirect?.route || null;
}

export function isPublicRoutePath(pathname: string): boolean {
  const route = getEffectiveRouteByPath(pathname);
  return !route || route.auth === 'public';
}

export function isRouteAccessibleToProfile(
  route: RouteRegistryEntry | null,
  profile: RouteProfile | null | undefined,
  options: AccessOptions = {}
): boolean {
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

export function hasRouteAccess(
  profile: RouteProfile | null | undefined,
  pathname: string,
  options: AccessOptions = {}
): boolean {
  const route = getEffectiveRouteByPath(pathname);
  return isRouteAccessibleToProfile(route, profile, options);
}

export function routeToRoles(pathname: string): string[] {
  const route = getEffectiveRouteByPath(pathname);
  return route?.roles || [];
}

export function getRoleHomeRoute(roleOrProfile: string | RouteProfile | null | undefined): string {
  // PR-27/28: route by Doctor.specialty, not User.role.
  // Removed homeForUsernames (was hardcoded emails).
  // Known specialties → dedicated panel; unknown → DoctorPanel (generic).
  if (roleOrProfile && typeof roleOrProfile === 'object') {
    const profile = roleOrProfile as RouteProfile;
    const specialty = String(profile.specialty || '').toLowerCase().trim();
    if (specialty) {
      const specialtyRouteMap: Record<string, string> = {
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
        if (route && isRouteAccessibleToProfile(route, profile)) {
          return specialtyRouteMap[specialty];
        }
      }
      // Unknown specialty (e.g. 'neurology') → fall through to role-based
    }
  }

  const roles = typeof roleOrProfile === 'string'
    ? [normalizeRole(roleOrProfile)]
    : getProfileRoles(roleOrProfile as RouteProfile);

  for (const preferredRole of ROLE_HOME_PRIORITY as string[]) {
    if (!roles.includes(preferredRole)) {
      continue;
    }

    const homeRoute = typedRegistry.find((route) => (route.homeForRoles || []).includes(preferredRole));
    if (homeRoute) {
      return homeRoute.path;
    }
  }

  return '/clinical/search';
}

export function getRoutesForRole(
  roleOrProfile: string | RouteProfile | null | undefined,
  options: AccessOptions = {}
): RouteRegistryEntry[] {
  const roleProfile: RouteProfile = typeof roleOrProfile === 'string' ? { role: roleOrProfile } : (roleOrProfile || {});
  return typedRegistry.filter((route) => isRouteAccessibleToProfile(route, roleProfile, options));
}

export function getVisibleRoutesForShell(
  shell: string,
  profile: RouteProfile | null | undefined,
  options: AccessOptions = {}
): RouteRegistryEntry[] {
  return typedRegistry.filter((route) => {
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
  }).sort((left, right) => {
    const leftNav = typeof left.nav === 'object' ? left.nav : null;
    const rightNav = typeof right.nav === 'object' ? right.nav : null;
    return (leftNav?.order || 0) - (rightNav?.order || 0);
  });
}

export function getAdminNavRoutes(
  profile: RouteProfile | null | undefined,
  options: AccessOptions = {}
): RouteRegistryEntry[] {
  return typedRegistry
    .filter((route) => route.group === 'admin' && typeof route.nav === 'object' && route.nav.sidebar)
    .filter((route) => isRouteAccessibleToProfile(route, profile, options))
    .sort((left, right) => {
      const leftNav = typeof left.nav === 'object' ? left.nav : null;
      const rightNav = typeof right.nav === 'object' ? right.nav : null;
      const leftSectionIndex = ADMIN_SECTION_ORDER.indexOf(leftNav?.section || '');
      const rightSectionIndex = ADMIN_SECTION_ORDER.indexOf(rightNav?.section || '');
      if (leftSectionIndex !== rightSectionIndex) {
        return (leftSectionIndex === -1 ? ADMIN_SECTION_ORDER.length : leftSectionIndex) -
          (rightSectionIndex === -1 ? ADMIN_SECTION_ORDER.length : rightSectionIndex);
      }
      return (leftNav?.order || 0) - (rightNav?.order || 0);
    });
}

export function getAdminNavSections(
  profile: RouteProfile | null | undefined,
  options: AccessOptions = {}
): SidebarSection[] {
  return getAdminNavRoutes(profile, options).reduce<SidebarSection[]>((sections, route) => {
    const routeNav = typeof route.nav === 'object' ? route.nav : null;
    const sectionName = routeNav?.section || 'General';
    const existingSection = sections.find((section) => section.title === sectionName);
    const item: SidebarItem = {
      id: route.id,
      to: route.path,
      label: routeNav?.label || route.title,
      icon: routeNav?.icon || 'circle',
      badge: routeNav?.badge,
      tooltip: routeNav?.tooltip,
      ariaLabel: routeNav?.ariaLabel,
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

export function getClinicalNavRoutes(
  profile: RouteProfile | null | undefined,
  options: AccessOptions = {}
): RouteRegistryEntry[] {
  return typedRegistry
    .filter((route) => route.group === 'clinical' && typeof route.nav === 'object' && route.nav.menu)
    .filter((route) => isRouteAccessibleToProfile(route, profile, options))
    .sort((left, right) => {
      const leftNav = typeof left.nav === 'object' ? left.nav : null;
      const rightNav = typeof right.nav === 'object' ? right.nav : null;
      return (leftNav?.order || 0) - (rightNav?.order || 0);
    });
}

export function getPublicRoutes(): RouteRegistryEntry[] {
  return typedRegistry.filter((route) => route.group === 'public');
}

export function getInternalDemoRoutes(): RouteRegistryEntry[] {
  return typedRegistry.filter((route) => route.group === 'internal-demo');
}

export function getRouteDocsSnapshot(): RouteDocsSnapshot {
  return buildRouteDocsSnapshot();
}

export function isInternalDemoEnabled(): boolean {
  return import.meta.env.VITE_ENABLE_INTERNAL_DEMO === '1';
}

export function getRouteChromeState(
  pathname: string,
  search = '',
  profile: RouteProfile | null = null
): RouteChromeState {
  const route = getEffectiveRouteByPath(pathname) || getCanonicalRouteById('not-found');
  const routeLayout: RouteLayout = route?.layout || {};
  const sidebarPresetKey = routeLayout.sidebarPreset || null;
  const sidebarPresetLookup = SIDEBAR_PRESETS as unknown as Record<string, SidebarPreset>;
  const sidebarPreset = sidebarPresetKey ? (sidebarPresetLookup[sidebarPresetKey] || null) : null;
  const searchParams = new URLSearchParams(search);

  let sidebarItems: SidebarItem[] = sidebarPreset?.items || [];
  // P-010 fix: support sectioned sidebar presets. If a preset declares `sections`
  // (array of { title, items }), we pass both `sidebarSections` and a flattened
  // `sidebarItems` (for backward compatibility with any consumer that still
  // reads .sidebarItems). Sidebar.jsx renders sections when present, else falls
  // back to the flat items list.
  let sidebarSections: SidebarSection[] | null = null;
  if (Array.isArray(sidebarPreset?.sections) && sidebarPreset.sections.length > 0) {
    sidebarSections = sidebarPreset.sections;
    // Flatten sections into sidebarItems for backward-compat consumers
    sidebarItems = sidebarPreset.sections.flatMap((section) => section.items || []);
  }
  if (sidebarPresetKey === 'admin') {
    sidebarItems = getAdminNavRoutes(profile, { internalDemoEnabled: isInternalDemoEnabled() }).map((navRoute) => {
      const navMeta = typeof navRoute.nav === 'object' ? navRoute.nav : null;
      return {
        id: navRoute.id,
        label: navMeta?.label || navRoute.title,
        icon: navMeta?.icon || 'circle',
        badge: navMeta?.badge,
        tooltip: navMeta?.tooltip,
        ariaLabel: navMeta?.ariaLabel,
        to: navRoute.path,
      };
    });
  }
  if (sidebarPresetKey === 'default') {
    sidebarItems = getClinicalNavRoutes(profile, { internalDemoEnabled: isInternalDemoEnabled() }).map((navRoute) => {
      const navMeta = typeof navRoute.nav === 'object' ? navRoute.nav : null;
      return {
        id: navRoute.id,
        label: navMeta?.label || navRoute.title,
        icon: navMeta?.icon || 'circle',
        badge: navMeta?.badge,
        tooltip: navMeta?.tooltip,
        ariaLabel: navMeta?.ariaLabel,
        to: navRoute.path,
      };
    });
  }

  const activeSidebarItem = routeLayout.activeSidebarItem ||
    searchParams.get(sidebarPreset?.queryParam || '') ||
    sidebarPreset?.defaultItem ||
    null;

  return {
    route,
    pageTitle: (route?.layout?.pageTitle as string) || route?.title || 'Clinic Management System',
    hideHeader: Boolean(routeLayout.hideHeader),
    hideSidebar: Boolean(routeLayout.hideSidebar || !sidebarPreset),
    fullscreen: Boolean(routeLayout.fullscreen),
    sidebarPreset,
    sidebarItems,
    sidebarSections,
    activeSidebarItem,
  };
}

export function getCompatibilityRedirects(): CompatibilityRedirect[] {
  return typedRegistry.flatMap((route) =>
    (route.legacyRedirectFrom || []).map((aliasPath) => ({
      aliasPath,
      routeId: route.id,
      targetPath: route.path,
    }))
  );
}
