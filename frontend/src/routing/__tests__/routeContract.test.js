import { describe, expect, it } from 'vitest';
import { renderRouteDocsMarkdown } from '../routeDocsSnapshot.js';
import { resolveSetupRedirect } from '../routeGuards.jsx';
import { ROUTE_REGISTRY, SIDEBAR_PRESETS } from '../routeRegistry.js';
import {
  getCompatibilityRedirects,
  getInternalDemoRoutes,
  getLegacyRedirectTarget,
  getRoleHomeRoute,
  getRouteDocsSnapshot,
  getRouteChromeState,
  isInternalDemoEnabled,
  isRouteAccessibleToProfile,
} from '../routeSelectors.js';

const PRODUCTION_ROLE_HOMES = {
  admin: '/admin',
  registrar: '/registrar',
  lab: '/lab',
  doctor: '/doctor',
  cashier: '/cashier',
  cardio: '/doctor/cardiology',
  derma: '/doctor/dermatology',
  dentist: '/doctor/dentistry',
  patient: '/patient',
};

const AI_SIDEBAR_BADGE = 'Черновик · не медицинское заключение';
const AI_SIDEBAR_ACCESSIBLE_COPY = /черновик, не диагноз, не медицинское заключение/i;

const ADMIN_CONTEXTUAL_ROUTE_IDS = [
  'admin-benefit-settings',
  'admin-wizard-settings',
  'admin-payment-providers',
  'admin-clinic-settings',
  'admin-queue-settings',
  'admin-telegram-settings',
  'admin-display-settings',
  'admin-user-select',
];

const CLINICAL_CONTEXTUAL_ROUTE_IDS = [
  'clinical-profile',
  'clinical-security',
  'clinical-two-factor',
  'clinical-visit-details',
  'clinical-pickup',
];

function assertAiSidebarDisclaimer(item) {
  expect(item.badge).toBe(AI_SIDEBAR_BADGE);
  expect(item.tooltip).toMatch(AI_SIDEBAR_ACCESSIBLE_COPY);
  expect(item.ariaLabel).toMatch(AI_SIDEBAR_ACCESSIBLE_COPY);
}

function getRouteById(routeId) {
  return ROUTE_REGISTRY.find((route) => route.id === routeId);
}

describe('route contract invariants', () => {
  it('keeps route ids unique and canonical paths singular', () => {
    const ids = new Set();
    const paths = new Set();

    ROUTE_REGISTRY.forEach((route) => {
      expect(ids.has(route.id)).toBe(false);
      expect(paths.has(route.path)).toBe(false);
      ids.add(route.id);
      paths.add(route.path);
    });
  });

  it('keeps admin routes under /admin', () => {
    ROUTE_REGISTRY.filter((route) => route.group === 'admin').forEach((route) => {
      expect(route.path.startsWith('/admin')).toBe(true);
    });
  });

  it('keeps internal demo routes out of navigation', () => {
    getInternalDemoRoutes().forEach((route) => {
      expect(route.nav).toBe(false);
    });
  });

  it('keeps internal demo routes disabled unless explicitly enabled', () => {
    const demoRoute = getInternalDemoRoutes()[0];

    expect(isInternalDemoEnabled()).toBe(false);
    expect(isRouteAccessibleToProfile(demoRoute, { role: 'Admin' }, { internalDemoEnabled: false })).toBe(false);
    expect(isRouteAccessibleToProfile(demoRoute, { role: 'Admin' }, { internalDemoEnabled: true })).toBe(true);
  });

  it('does not assign roles to public routes', () => {
    ROUTE_REGISTRY.filter((route) => route.auth === 'public').forEach((route) => {
      expect(route.roles).toEqual([]);
    });
  });

  it('does not expose callback routes in navigation', () => {
    ROUTE_REGISTRY.filter((route) => route.surface === 'callback').forEach((route) => {
      expect(route.nav).toBe(false);
    });
  });

  it('requires at least one role for every role-scoped route', () => {
    ROUTE_REGISTRY.filter((route) => route.auth === 'role-scoped').forEach((route) => {
      expect(route.roles.length).toBeGreaterThan(0);
    });
  });

  it('assigns exactly one canonical home route per production role', () => {
    Object.entries(PRODUCTION_ROLE_HOMES).forEach(([role, expectedPath]) => {
      expect(getRoleHomeRoute(role)).toBe(expectedPath);
    });
  });

  it('supports specialist username home overrides when backend role is generic', () => {
    expect(getRoleHomeRoute({ username: 'cardio@example.com', role: 'Doctor' })).toBe('/doctor/cardiology');
    expect(getRoleHomeRoute({ username: 'derma@example.com', role: 'Doctor' })).toBe('/doctor/dermatology');
    expect(getRoleHomeRoute({ username: 'dentist@example.com', role: 'Doctor' })).toBe('/doctor/dentistry');
  });

  it('keeps compatibility aliases separate from canonical paths', () => {
    const canonicalPaths = new Set(ROUTE_REGISTRY.map((route) => route.path));

    getCompatibilityRedirects().forEach((redirect) => {
      expect(canonicalPaths.has(redirect.aliasPath)).toBe(false);
    });
  });

  it('labels AI sidebar navigation as draft support, not a diagnosis', () => {
    const presetAiItems = Object.values(SIDEBAR_PRESETS)
      .flatMap((preset) => preset.items || [])
      .filter((item) => item.id === 'ai' || item.id === 'ai-assistant');

    expect(presetAiItems).toHaveLength(4);
    presetAiItems.forEach(assertAiSidebarDisclaimer);

    const adminAiRoute = ROUTE_REGISTRY.find((route) => route.id === 'admin-ai-settings');
    assertAiSidebarDisclaimer(adminAiRoute.nav);

    const adminChrome = getRouteChromeState('/admin/ai-settings', '', { role: 'Admin' });
    const adminAiItem = adminChrome.sidebarItems.find((item) => item.id === 'admin-ai-settings');

    assertAiSidebarDisclaimer(adminAiItem);
  });

  it('keeps admin contextual routes registered and out of admin sidebar navigation', () => {
    const adminProfile = { role: 'Admin' };
    const adminChrome = getRouteChromeState('/admin', '', adminProfile);
    const adminSidebarIds = new Set(adminChrome.sidebarItems.map((item) => item.id));
    const adminSidebarTargets = new Set(adminChrome.sidebarItems.map((item) => item.to));

    ADMIN_CONTEXTUAL_ROUTE_IDS.forEach((routeId) => {
      const route = getRouteById(routeId);

      expect(route).toBeTruthy();
      expect(route.group).toBe('admin');
      expect(route.nav).toBe(false);
      expect(isRouteAccessibleToProfile(route, adminProfile)).toBe(true);
      expect(adminSidebarIds.has(route.id)).toBe(false);
      expect(adminSidebarTargets.has(route.path)).toBe(false);
    });
  });

  it('keeps clinical contextual routes registered and out of default sidebar navigation', () => {
    const doctorProfile = { role: 'Doctor' };
    const clinicalChrome = getRouteChromeState('/clinical/search', '', doctorProfile);
    const clinicalSidebarIds = new Set(clinicalChrome.sidebarItems.map((item) => item.id));
    const clinicalSidebarTargets = new Set(clinicalChrome.sidebarItems.map((item) => item.to));

    CLINICAL_CONTEXTUAL_ROUTE_IDS.forEach((routeId) => {
      const route = getRouteById(routeId);

      expect(route).toBeTruthy();
      expect(route.group).toBe('clinical');
      expect(route.nav).toBe(false);
      expect(isRouteAccessibleToProfile(route, doctorProfile)).toBe(true);
      expect(clinicalSidebarIds.has(route.id)).toBe(false);
      expect(clinicalSidebarTargets.has(route.path)).toBe(false);
    });
  });

  it('keeps route-derived admin and default sidebar targets backed by canonical routes', () => {
    const canonicalPaths = new Set(ROUTE_REGISTRY.map((route) => route.path));
    const routeDerivedSidebarItems = [
      ...getRouteChromeState('/admin', '', { role: 'Admin' }).sidebarItems,
      ...getRouteChromeState('/clinical/search', '', { role: 'Doctor' }).sidebarItems,
    ];

    expect(routeDerivedSidebarItems.length).toBeGreaterThan(0);
    routeDerivedSidebarItems.forEach((item) => {
      expect(item.to).toBeTruthy();
      expect(canonicalPaths.has(item.to)).toBe(true);
    });
  });
});

describe('redirect and setup policies', () => {
  it('redirects legacy clinical urls to canonical destinations', () => {
    expect(getLegacyRedirectTarget('/registrar-panel')?.targetPath).toBe('/registrar');
    expect(getLegacyRedirectTarget('/settings')?.targetPath).toBe('/admin/settings');
    expect(getLegacyRedirectTarget('/payment/test')?.targetPath).toBe('/internal-demo/payment-test');
  });

  it('applies setup precedence without loops', () => {
    expect(resolveSetupRedirect('/admin', false)).toBe('/setup');
    expect(resolveSetupRedirect('/clinical/search', false)).toBe('/setup');
    expect(resolveSetupRedirect('/queue/join', false)).toBe(null);
    expect(resolveSetupRedirect('/setup', true)).toBe('/login');
    expect(resolveSetupRedirect('/login', true)).toBe(null);
  });
});

describe('docs snapshot', () => {
  it('publishes canonical routing documentation from the registry', () => {
    const snapshot = getRouteDocsSnapshot();
    const markdown = renderRouteDocsMarkdown(snapshot);

    expect(snapshot.groups.admin.some((route) => route.path === '/admin/settings')).toBe(true);
    expect(snapshot.groups.clinical.some((route) => route.path === '/clinical/profile')).toBe(true);
    expect(markdown).toContain('Compatibility Redirects');
    expect(markdown).toContain('/registrar');
    expect(markdown).toContain('/admin/settings');
  });
});
