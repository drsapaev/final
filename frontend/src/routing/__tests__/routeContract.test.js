import { describe, expect, it } from 'vitest';
import { renderRouteDocsMarkdown } from '../routeDocsSnapshot.js';
import { resolveSetupRedirect } from '../routeGuards.jsx';
import { ROUTE_REGISTRY } from '../routeRegistry.js';
import { getCompatibilityRedirects, getInternalDemoRoutes, getLegacyRedirectTarget, getRoleHomeRoute, getRouteDocsSnapshot } from '../routeSelectors.js';

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
